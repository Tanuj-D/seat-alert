"""Run the seat checker as its own process: python -m app.run_checker

The web server runs database migrations at startup, so start it first.
"""

import logging
import time

from app import config
from app.checker import run_check_once


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        started = time.monotonic()
        try:
            sent = run_check_once()
            logging.info("Check complete in %.1fs, %d alerts sent",
                         time.monotonic() - started, sent)
        except Exception:
            logging.exception("Seat check failed")
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
