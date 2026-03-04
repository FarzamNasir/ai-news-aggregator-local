"""
Create all database tables.

Usage:
    uv run python -m app.database.create_tables
"""

import logging
from dotenv import load_dotenv

load_dotenv()

from app.database.connection import engine
from app.database.models import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def create_tables():
    logger.info("Creating tables...")
    Base.metadata.create_all(engine)
    logger.info("Done! Tables created successfully.")

    # List created tables
    for table_name in Base.metadata.tables:
        logger.info("  - %s", table_name)


if __name__ == "__main__":
    create_tables()
