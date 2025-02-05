import re

from telegram import Bot

from src.tgbot.constants import UserType
from src.tgbot.handlers.treasury.constants import TrxType
from src.tgbot.handlers.treasury.payments import pay_if_not_paid_with_alert
from src.tgbot.logs import log
from src.tgbot.senders.invite import send_successfull_invitation_alert
from src.tgbot.service import get_tg_user_by_id, get_user_by_id, update_user

LINK_UNDER_MEME_PATTERN = r"s_\d+_\d+"


async def handle_deep_link_used(
    bot: Bot, invited_user: dict, invited_user_name: str, deep_link: str
):
    """
    E.g. if user was invited, send a msg to invited about used invitation
    """

    # TODO: log all deep link used
    if re.match(LINK_UNDER_MEME_PATTERN, deep_link):
        _, user_id, _ = deep_link.split("_")
        invitor_user_id = int(user_id)

        if invitor_user_id == invited_user["id"]:
            return  # clicked on own link

        invitor_user = await get_user_by_id(invitor_user_id)
        if not invitor_user:
            return  # user with this id doesn't exist

        if not invited_user.get("inviter_id"):
            await update_user(invited_user["id"], inviter_id=invitor_user_id)
            # TODO: should we send to inviter alert message?

        if invitor_user["type"] != UserType.WAITLIST and invited_user["type"] in [
            UserType.WAITLIST,
            UserType.BLOCKED_BOT,
        ]:
            await update_user(invited_user["id"], type=UserType.USER)

            await send_successfull_invitation_alert(invitor_user_id, invited_user_name)
            invitor_user_tg = await get_tg_user_by_id(invitor_user_id)
            is_premium = invitor_user_tg and invitor_user_tg.get("is_premium")

            await pay_if_not_paid_with_alert(
                bot,
                invitor_user_id,
                TrxType.USER_INVITER_PREMIUM if is_premium else TrxType.USER_INVITER,
                external_id=str(invited_user["id"]),
            )

            await log(f"🤝 #{invitor_user_id} invited {invited_user_name}")
