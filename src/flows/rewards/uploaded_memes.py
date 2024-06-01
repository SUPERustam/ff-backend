import asyncio
from datetime import datetime

import telegram

from prefect import flow, get_run_logger

from src.flows.rewards.service import get_all_uploaded_memes_weerly_ru
from src.tgbot.bot import bot
from src.tgbot.constants import (
    TELEGRAM_CHANNEL_RU_CHAT_ID,
    TELEGRAM_CHANNEL_RU_LINK,
)
from src.tgbot.handlers.treasury.constants import TrxType
from src.tgbot.handlers.treasury.payments import pay_if_not_paid_with_alert
from src.tgbot.logs import log


@flow(name="Reward RU users for weekly top uploaded memes")
async def reward_ru_users_for_weekly_top_uploaded_memes():
    logger = get_run_logger()

    logger.info("Going to reward users for weekly top uploaded memes")

    """
    # TODO:
    1. Get all uploaded memes this week.
    2. Calculate some stats:
       - uploaded memes
       - users who uploaded memes
       - total views
       - average like %
    3. Get top 5 memes by like %.
    4. Reward users:
       - 500 🍔 for 1st plac
       - 300 🍔 for 2nd plac
       - 200 🍔 for 3rd plac
       - 100 🍔 for 4th plac
       - 50 🍔 for 5th plac
    5. Notify users about rewards:
       - send message to a channel with top 5 memes.
       - for meme authors which doesn't follow the channel,
         send a message with a link to the post in channel.
         with stats of user's uploaded memes
    """

    uploaded_memes = await get_all_uploaded_memes_weerly_ru()
    logger.info(f"Received {len(uploaded_memes)} uploaded memes")

    if len(uploaded_memes) < 5:
        await log("Not enough memes to reward users: only {len(uploaded_memes)}")
        return

    nuploaded = len(uploaded_memes)
    nusers = len(set(m["author_id"] for m in uploaded_memes))
    total_views = sum(m["nmemes_sent"] for m in uploaded_memes)
    likes = sum(m["nlikes"] for m in uploaded_memes)
    dislikes = sum(m["ndislikes"] for m in uploaded_memes)
    avg_like = likes / (likes + dislikes) if likes + dislikes > 0 else 0

    logger.info(
        f"Uploaded memes: {nuploaded}, users: {nusers}, total views: {total_views}, avg like: {avg_like}",
    )
    today = datetime.today().date().strftime("%Y-%m-%d")

    ###########################
    # reward top authors

    top_memes = sorted(
        uploaded_memes,
        key=lambda m: m["nlikes"] / (m["nlikes"] + m["ndislikes"])
        if m["nlikes"] + m["ndislikes"] > 0
        else 0,
        reverse=True,
    )[:5]

    for i, top_meme in enumerate(top_memes):
        if i == 0:
            type = TrxType.UPLOADER_TOP_WEEKLY_1
        elif i == 1:
            type = TrxType.UPLOADER_TOP_WEEKLY_2
        elif i == 2:
            type = TrxType.UPLOADER_TOP_WEEKLY_3
        elif i == 3:
            type = TrxType.UPLOADER_TOP_WEEKLY_4
        elif i == 4:
            type = TrxType.UPLOADER_TOP_WEEKLY_5
        else:
            continue

        await pay_if_not_paid_with_alert(
            bot,
            top_meme["author_id"],
            type,
            enternal_id=today,
        )

    # send message to tgchannelru

    channel_text = f"""
🏆 ТОП-5 загруженных мемов недели

🥇 - {top_memes[0]["nickname"] or '???'}
🥈 - {top_memes[1]["nickname"] or '???'}
🥉 - {top_memes[2]["nickname"] or '???'}
🏅 - {top_memes[3]["nickname"] or '???'}
🏅 - {top_memes[4]["nickname"] or '???'}

📥 Загружено мемов: {nuploaded}
👤 Пользователями: {nusers}
👁️ Просмотры: {total_views}
👍 Доля лайков: {round(likes * 100. / (likes + dislikes))}%
    """

    ms = await bot.send_media_group(
        TELEGRAM_CHANNEL_RU_CHAT_ID,
        [telegram.InputMediaPhoto(media=m["telegram_file_id"]) for m in top_memes],
        caption=channel_text,
        parse_mode="HTML",
    )

    message_link = f"{TELEGRAM_CHANNEL_RU_LINK}/{ms[0].id}"

    # send message to authors

    author_ids = set(m["author_id"] for m in top_memes)
    logger.info(f"Going to notify {len(author_ids)} authors about rewards")
    for author_id in author_ids:
        user_uploaded_memes = [m for m in uploaded_memes if m["author_id"] == author_id]
        likes = sum(m["nlikes"] for m in user_uploaded_memes)
        dislikes = sum(m["ndislikes"] for m in user_uploaded_memes)
        like_prc = round(likes * 100.0 / (likes + dislikes))

        user_text = f"""
Стата по загруженным тобой мемам:
📥 Загружено мемов: {len(user_uploaded_memes)}
👁️ Просмотры: {sum(m["nviews"] for m in user_uploaded_memes)}
👍 Доля лайков: {like_prc}%

Смотри топ-5 мемов недели в нашем канале: {message_link}
        """
        try:
            await bot.send_message(author_id, user_text)
        except Exception as e:
            logger.error(f"Failed to send message to {author_id}: {e}")

        await asyncio.sleep(2)
