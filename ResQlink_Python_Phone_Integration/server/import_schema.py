import os, sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).with_name(".env"), override=True)
sql = Path(sys.argv[1]).read_text(encoding="utf-8")
with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as con:
    con.execute(sql)
print("schema imported")