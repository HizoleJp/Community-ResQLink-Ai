import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).with_name(".env"))
url = os.getenv("DATABASE_URL", "").strip()
if not url.startswith("postgres"):
    raise SystemExit("DATABASE_URL is missing or not a postgresql:// URL")

with psycopg.connect(url) as con:
    with con.cursor() as cur:
        cur.execute("SELECT current_database()")
        print("Connected to:", cur.fetchone()[0])
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY 1"
        )
        for (name,) in cur.fetchall():
            print(" -", name)