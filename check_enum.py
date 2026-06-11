"""Check what enum values Postgres actually has for sourcetype."""
import os
os.environ["DATABASE_URL"] = (
    "postgresql://aggregator:y9UilXdpXU22yex2aVP3gxkE8DjYhPt3"
    "@dpg-d8kn24ldt1ts73a8e8qg-a.frankfurt-postgres.render.com/news_aggregator_i9me"
)

from sqlalchemy import text
from app.database.connection import engine

with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT enumlabel FROM pg_enum e "
        "JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = 'sourcetype' "
        "ORDER BY e.enumsortorder"
    ))
    print("Postgres sourcetype enum values:")
    for row in rows:
        print(f"  '{row[0]}'")
