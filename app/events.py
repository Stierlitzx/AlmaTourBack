"""
Event-driven analytics worker.

DEV  (current):  FastAPI BackgroundTasks — runs in-process after response is sent.
                 Simple, zero dependencies, but lost on crash.

PRODUCTION recommendation:
  Replace with a Redis-backed queue.  Two popular options:
    a) ARQ  (async, built for asyncio)  — pip install arq
       • Define a worker function, push job IDs via arq.create_pool()
       • Run: arq app.worker.WorkerSettings
    b) Celery + Redis broker  — pip install celery redis
       • More ecosystem support; easier if you already use Celery elsewhere.

  Either approach survives server crashes, scales horizontally, and gives
  you retry semantics and dead-letter queues out of the box.
  
  The interface below is intentionally thin so swapping is a one-liner.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud

logger = logging.getLogger("AlmaTour.events")


async def process_booking_confirmed(
    h3_region: str,
    revenue: float,
    booking_id: int,
    db: AsyncSession,
) -> None:
    """
    Called as a FastAPI BackgroundTask.
    Updates H3 regional analytics after a booking is confirmed.
    """
    try:
        async with db:  # use passed session in its own transaction
            await crud.upsert_h3_analytics(db, h3_region, revenue)
            await db.commit()
        logger.info(
            "EVENT booking_confirmed processed | booking=%s region=%s revenue=%.2f",
            booking_id, h3_region, revenue,
        )
    except Exception as exc:
        logger.error(
            "EVENT processing failed | booking=%s error=%s", booking_id, exc, exc_info=True
        )
        # In production, push to dead-letter queue here instead of silently dropping
