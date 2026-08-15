"""Asia/Hong_Kong daily incremental synchronization process."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta

from laoliuliu.config import Settings, get_settings
from laoliuliu.db import SessionLocal
from laoliuliu.ingestion import synchronize_current
from laoliuliu.source import SourceClient

logger = logging.getLogger("laoliuliu.scheduler")


def seconds_until_next_run(now: datetime, settings: Settings) -> float:
    """Calculate the next 21:35 Asia/Hong_Kong trigger delay."""

    local_now = now.astimezone(settings.zone)
    candidate = local_now.replace(
        hour=settings.sync_hour,
        minute=settings.sync_minute,
        second=0,
        microsecond=0,
    )
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return max(0.0, (candidate - local_now).total_seconds())


def run_once(settings: Settings) -> None:
    """Run one scheduled sync with bounded empty-result retries."""

    client = SourceClient(settings)
    attempts = settings.sync_empty_retries + 1
    for attempt in range(attempts):
        with SessionLocal() as db:
            result = synchronize_current(db, client, settings)
        logger.info(
            json.dumps(
                {
                    "event": "source.sync.completed",
                    "attempt": attempt + 1,
                    "inserted": result.inserted,
                    "skipped": result.skipped,
                    "run_id": result.run_id,
                },
                sort_keys=True,
            )
        )
        if result.inserted > 0 or attempt == attempts - 1:
            return
        time.sleep(settings.sync_empty_retry_seconds)


def entrypoint() -> None:
    """Run the persistent daily scheduler."""

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    while True:
        delay = seconds_until_next_run(datetime.now(settings.zone), settings)
        logger.info(
            json.dumps(
                {"event": "scheduler.waiting", "seconds": round(delay)},
                sort_keys=True,
            )
        )
        time.sleep(delay)
        try:
            run_once(settings)
        except Exception:
            logger.exception("scheduled source synchronization failed")


if __name__ == "__main__":
    entrypoint()
