"""Run the seat checker on a loop: python -m app.run_checker"""

import logging
import os
import time

from app.checker import check_watches
from app.db import SessionLocal, init_db

INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db()
    while True:
        with SessionLocal() as session:
            sent = check_watches(session)
        logging.info("Check complete, %d alerts sent", sent)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
