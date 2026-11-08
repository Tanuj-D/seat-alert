"""Run the seat checker on a loop: python -m app.run_checker"""

import logging
import time

from app import config
from app.checker import check_watches
from app.db import SessionLocal, init_db


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    while True:
        started = time.monotonic()
        with SessionLocal() as session:
            sent = check_watches(session, delay=config.CHECK_REQUEST_DELAY_SECONDS)
        logging.info("Check complete in %.1fs, %d alerts sent", time.monotonic() - started, sent)
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
