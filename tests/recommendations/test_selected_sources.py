from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from src import redis
from src.database import (engine, meme, meme_source, meme_stats, user,
                          user_language, user_meme_reaction)
from src.recommendations.candidates import get_selected_sources
from src.recommendations.meme_queue import generate_cold_start_recommendations


@pytest_asyncio.fixture()
async def conn():
    async with engine.connect() as conn:

        await conn.execute(
            insert(user),
            [{'id': 1, 'type': 'user'}, {'id': 21, 'type': 'user'}]
        )
        await conn.execute(
            insert(meme_source),
            {'id': 1, 'type': 'telegram', 'url': '111', 'status': 'parsing_enabled', 'created_at': datetime(2024, 1, 1)}
        )
        meme_basic = {
            'raw_meme_id': 1, 'type': 'image', 'telegram_image_id': '111', 'caption': '111', 'meme_source_id': 1,
            'published_at': datetime(2024, 1, 1), 'status': 'ok', 'language_code': 'ru',
        }
        good_meme_1 = 6470439
        good_meme_2 = 7648698
        seen_meme = 6522792
        bad_meme = 1
        meme_ids = [good_meme_1, good_meme_2, seen_meme, bad_meme]

        await conn.execute(
            insert(meme),
            [meme_basic.copy() | {'id': meme_id, 'raw_meme_id': meme_id} for meme_id in meme_ids]
        )
        await conn.execute(
            insert(meme_stats),
        [{'meme_id': meme_id, 'sec_to_react': 0, 'nlikes': 10, 'ndislikes': 10} for meme_id in meme_ids],
        )
        await conn.execute(
            insert(user_language),
            [
                {'user_id': 1, 'language_code': 'ru', 'created_at': datetime(2024, 1, 1)},
                {'user_id': 21, 'language_code': 'en', 'created_at': datetime(2024, 1, 1)},
                {'user_id': 21, 'language_code': 'es', 'created_at': datetime(2024, 1, 1)}
            ]
        )
        await conn.execute(
            insert(user_meme_reaction),
            [
                {'user_id': 1, 'meme_id': seen_meme, 'reaction_id': 1, 'recommended_by': '111', 'sent_at': datetime(2024, 1, 1)},
                {'user_id': 21, 'meme_id': seen_meme, 'reaction_id': 1, 'recommended_by': '111', 'sent_at': datetime(2024, 1, 1)}
            ]
        )

        await conn.commit()
        yield conn

        await conn.execute(delete(user_meme_reaction))
        await conn.execute(delete(user_language))
        await conn.execute(delete(meme_stats))
        await conn.execute(delete(meme))
        await conn.execute(delete(meme_source))
        await conn.execute(delete(user))
        await conn.commit()

        queue_key = redis.get_meme_queue_key(1)
        await redis.delete_by_key(queue_key)
        queue_key = redis.get_meme_queue_key(51)
        await redis.delete_by_key(queue_key)

        # TODO: redis sends the runtime error after the test succeeds
        # RuntimeError: Event loop is closed


@pytest.mark.asyncio
async def test_selected_sources(conn: AsyncConnection):
    recs = await get_selected_sources(1, 10)
    assert len(recs) == 2


@pytest.mark.asyncio
async def test_meme_queue(conn: AsyncConnection):
    user_id = 1
    await generate_cold_start_recommendations(user_id)
    queue_key = redis.get_meme_queue_key(user_id)
    recs = await redis.get_all_memes_in_queue_by_key(queue_key)
    assert len(recs) == 2
    assert recs[0]['recommended_by'] == 'selected_sources_240513'

    user_id = 21
    await generate_cold_start_recommendations(user_id)
    queue_key = redis.get_meme_queue_key(user_id)
    recs = await redis.get_all_memes_in_queue_by_key(queue_key)
    assert len(recs) == 0