from datetime import datetime, timezone
import base64
import binascii
from contextlib import contextmanager
import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

DB_PATH = Path(__file__).with_name("resqlink.db")
load_dotenv(Path(__file__).with_name(".env"))

import io
import cloudinary
import cloudinary.uploader
from fastapi.concurrency import run_in_threadpool

cloudinary.config(secure=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
MYSQL_ENABLED = DATABASE_URL.startswith(("mysql://", "mysql+pymysql://"))
PG_ENABLED = DATABASE_URL.startswith(("postgres://", "postgresql://"))
UPLOAD_DIR = Path(__file__).with_name("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
SUPER_ADMIN_TOKEN = os.getenv("SUPER_ADMIN_TOKEN", "").strip()
BOOTSTRAP_ADMIN_TOKENS = (
    {
        "account_key": "bootstrap:mdrrmo",
        "name": "MDRRMO",
        "organization": "mdrrmo",
        "token": os.getenv("MDRRMO_ADMIN_TOKEN", "").strip(),
    },
    {
        "account_key": "bootstrap:cityhall-bacoor",
        "name": "Bacoor City Hall",
        "organization": "cityhall_bacoor",
        "token": os.getenv("CITYHALL_ADMIN_TOKEN", "").strip(),
    },
)
BACOOR_BOUNDS = (14.35, 14.52, 120.90, 121.03)

app = FastAPI(title="ResQlink Python API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

class HazardCreate(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=10, max_length=280)
    lat: float
    lng: float

class SosCreate(BaseModel):
    lat: float
    lng: float
    label: str = Field(default="Current phone location", max_length=160)

class ReportPayload(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=10, max_length=280)
    lat: float
    lng: float
    image_base64: Optional[str] = None
    image_mime: Optional[str] = None

class AnnouncementPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)
    level: str = Field(default="info", max_length=20)
    audience: str = Field(default="all", max_length=40)

class AdminAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    organization: str = Field(pattern="^(mdrrmo|cityhall_bacoor|other_lgu|other_org)$")
    organization_name: Optional[str] = Field(default=None, max_length=120)

class AdminAccountUpdate(BaseModel):
    active: bool

class EvacuationCenterPayload(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: Optional[str] = Field(default=None, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    capacity: int = Field(default=0, ge=0)
    occupancy: int = Field(default=0, ge=0)
    status: str = Field(default="open", pattern="^(open|full|closed)$")

class UserProfilePayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=80)
    phone_number: Optional[str] = Field(default=None, max_length=20)
    home_address: Optional[str] = Field(default=None, max_length=200)

class EmergencyContactPayload(BaseModel):
    contact_name: str = Field(min_length=1, max_length=80)
    contact_phone: str = Field(min_length=5, max_length=20)
    relationship: Optional[str] = Field(default=None, max_length=50)

def now():
    return datetime.now(timezone.utc).isoformat()

def upload_photo(content: bytes) -> dict:
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(content), folder="resqlink/reports", resource_type="image"
        )
    except Exception:
        raise HTTPException(502, "Photo upload failed. Please try again.")
    return {"url": result["secure_url"], "public_id": result["public_id"]}

def delete_photo(public_id):
    if not public_id:
        return
    try:
        cloudinary.uploader.destroy(public_id)
    except Exception:
        pass

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

@contextmanager
def mysql_db():
    parsed = urlparse(DATABASE_URL)
    connection = pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=parsed.path.lstrip("/"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

@contextmanager
def pg_db():
    # Commits when the block ends normally, rolls back on error, always closes.
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15) as connection:
        yield connection

def placeholders(query: str) -> str:
    return query.replace("?", "%s")

def mysql_report_json(row):
    return {
        "id": str(row["report_id"]),
        "type": row["hazard_type"],
        "description": row["description"] or "",
        "time": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        "status": {"pending": "Pending verification", "verified": "Community verified"}.get(row["status"], row["status"].title()),
        "lat": float(row["latitude"]),
        "lng": float(row["longitude"]),
        "photo_url": row["image_url"],
    }

def guest_user_id(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM users WHERE email=%s LIMIT 1", ("guest@example.com",))
        row = cursor.fetchone()
        if row:
            return int(row["user_id"])
        cursor.execute(
            "INSERT INTO users(full_name,email,phone_number,password_hash,role) VALUES(%s,%s,%s,%s,%s)",
            ("ResQLink Guest", "guest@example.com", "0000000000", "not-for-login", "guest"),
        )
        return int(cursor.lastrowid)

def pg_guest_user_id(con) -> int:
    row = con.execute(
        "SELECT user_id FROM users WHERE email=%s LIMIT 1", ("guest@example.com",)
    ).fetchone()
    if row:
        return int(row["user_id"])
    row = con.execute(
        "INSERT INTO users(full_name,email,phone_number,password_hash,role) "
        "VALUES(%s,%s,%s,%s,%s) RETURNING user_id",
        ("ResQLink Guest", "guest@example.com", "0000000000", "not-for-login", "guest"),
    ).fetchone()
    return int(row["user_id"])

def normalize_hazard_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "flooding": "flood",
        "typhoon": "typhoon",
        "fire": "fire",
        "wildfire": "fire",
        "landslide": "landslide",
        "structural_damage": "structural_damage",
    }
    return aliases.get(normalized, "other")

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def seed_admin_accounts():
    if PG_ENABLED:
        with pg_db() as con:
            for account in BOOTSTRAP_ADMIN_TOKENS:
                if account["token"]:
                    con.execute(
                        """INSERT INTO admin_accounts (account_key, name, organization, token_hash)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (account_key) DO UPDATE SET token_hash = EXCLUDED.token_hash""",
                        (
                            account["account_key"],
                            account["name"],
                            account["organization"],
                            token_hash(account["token"]),
                        ),
                    )
        return

    if MYSQL_ENABLED:
        with mysql_db() as con:
            with con.cursor() as cursor:
                cursor.execute("""CREATE TABLE IF NOT EXISTS shelters(
                    shelter_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(150) NOT NULL,
                    address VARCHAR(255) NULL,
                    latitude DECIMAL(10, 8) NOT NULL,
                    longitude DECIMAL(11, 8) NOT NULL,
                    capacity INT NOT NULL DEFAULT 0,
                    current_occupancy INT NOT NULL DEFAULT 0,
                    status ENUM('open', 'full', 'closed') DEFAULT 'open'
                ) CHARACTER SET utf8mb4""")
                cursor.execute("SHOW COLUMNS FROM shelters LIKE 'address'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE shelters ADD COLUMN address VARCHAR(255) NULL")
                cursor.execute("""CREATE TABLE IF NOT EXISTS admin_accounts(
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    account_key VARCHAR(80) NOT NULL UNIQUE,
                    name VARCHAR(120) NOT NULL,
                    organization VARCHAR(30) NOT NULL,
                    organization_name VARCHAR(120) NULL,
                    token_hash CHAR(64) NOT NULL UNIQUE,
                    active TINYINT(1) NOT NULL DEFAULT 1,
                    deleted TINYINT(1) NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL
                ) CHARACTER SET utf8mb4""")
                cursor.execute("SHOW COLUMNS FROM admin_accounts LIKE 'organization_name'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE admin_accounts ADD COLUMN organization_name VARCHAR(120) NULL")
                for account in BOOTSTRAP_ADMIN_TOKENS:
                    if account["token"]:
                        cursor.execute(
                            """INSERT IGNORE INTO admin_accounts
                            (account_key,name,organization,token_hash,active,deleted,created_at)
                            VALUES(%s,%s,%s,%s,1,0,%s)""",
                            (
                                account["account_key"],
                                account["name"],
                                account["organization"],
                                token_hash(account["token"]),
                                now(),
                            ),
                        )
        return

    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS admin_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            organization TEXT NOT NULL,
            organization_name TEXT,
            token_hash TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        admin_columns = {row["name"] for row in con.execute("PRAGMA table_info(admin_accounts)")}
        if "organization_name" not in admin_columns:
            con.execute("ALTER TABLE admin_accounts ADD COLUMN organization_name TEXT")
        for account in BOOTSTRAP_ADMIN_TOKENS:
            if account["token"]:
                con.execute(
                    """INSERT OR IGNORE INTO admin_accounts
                    (account_key,name,organization,token_hash,active,deleted,created_at)
                    VALUES(?,?,?,?,1,0,?)""",
                    (
                        account["account_key"],
                        account["name"],
                        account["organization"],
                        token_hash(account["token"]),
                        now(),
                    ),
                )

def init_db():
    if PG_ENABLED:
        with pg_db() as con:
            con.execute("SELECT 1")
        seed_admin_accounts()
        return

    if MYSQL_ENABLED:
        with mysql_db() as con:
            with con.cursor() as cursor:
                cursor.execute("SELECT 1")
        seed_admin_accounts()
        return

    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS hazards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            created_at TEXT NOT NULL,
            photo_url TEXT
        )""")
        columns = {row["name"] for row in con.execute("PRAGMA table_info(hazards)")}
        if "photo_url" not in columns:
            con.execute("ALTER TABLE hazards ADD COLUMN photo_url TEXT")
        con.execute("""CREATE TABLE IF NOT EXISTS sos_signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            label TEXT NOT NULL,
            active INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS system_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_taken TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS announcements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'info',
            audience TEXT NOT NULL DEFAULT 'all',
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS user_profiles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone_number TEXT,
            home_address TEXT,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS emergency_contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_name TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            relationship TEXT,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS admin_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            organization TEXT NOT NULL,
            organization_name TEXT,
            token_hash TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        admin_columns = {row["name"] for row in con.execute("PRAGMA table_info(admin_accounts)")}
        if "organization_name" not in admin_columns:
            con.execute("ALTER TABLE admin_accounts ADD COLUMN organization_name TEXT")
        con.execute("""CREATE TABLE IF NOT EXISTS evacuation_centers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 0,
            occupancy INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open'
        )""")
        for account in BOOTSTRAP_ADMIN_TOKENS:
            if account["token"]:
                con.execute(
                    """INSERT OR IGNORE INTO admin_accounts
                    (account_key,name,organization,token_hash,active,deleted,created_at)
                    VALUES(?,?,?,?,1,0,?)""",
                    (
                        account["account_key"],
                        account["name"],
                        account["organization"],
                        token_hash(account["token"]),
                        now(),
                    ),
                )
        if con.execute("SELECT COUNT(*) FROM hazards").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO hazards(type,description,status,lat,lng,created_at) VALUES(?,?,?,?,?,?)",
                ("Severe Flash Flooding",
                 "Heavy rainfall is causing rapid street flooding. Vehicles are advised to use an alternate route.",
                 "Community verified", 14.41, 120.945, now())
            )
        if con.execute("SELECT COUNT(*) FROM announcements").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO announcements(title,message,level,audience,created_at) VALUES(?,?,?,?,?)",
                ("Weather advisory",
                 "Heavy rains and flash flooding are expected in Bacoor; use caution when traveling and monitor local guidance.",
                 "warning", "all", now()),
            )
            con.execute(
                "INSERT INTO announcements(title,message,level,audience,created_at) VALUES(?,?,?,?,?)",
                ("Evacuation coordination",
                 "If you are in a flooded or unsafe area, proceed to the nearest approved evacuation center or emergency shelter.",
                 "info", "all", now()),
            )
        if con.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO user_profiles(full_name,phone_number,home_address,created_at) VALUES(?,?,?,?)",
                ("Guest User", "09000000000", "Bacoor, Cavite", now()),
            )
        if con.execute("SELECT COUNT(*) FROM emergency_contacts").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO emergency_contacts(contact_name,contact_phone,relationship,created_at) VALUES(?,?,?,?)",
                ("Family Member", "09171234567", "Mother", now()),
            )

def log_event(action: str):
    if PG_ENABLED:
        with pg_db() as con:
            con.execute("INSERT INTO system_logs(action_taken) VALUES (%s)", (action[:255],))
        return

    if MYSQL_ENABLED:
        with mysql_db() as con:
            with con.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO system_logs(action_taken) VALUES(%s)",
                    (action[:255],),
                )
        return

    with db() as con:
        con.execute(
            "INSERT INTO system_logs(action_taken,created_at) VALUES(?,?)",
            (action[:255], now()),
        )

def get_logs(limit: int = 100):
    safe_limit = max(1, min(limit, 200))
    if PG_ENABLED:
        with pg_db() as con:
            rows = con.execute(
                'SELECT log_id AS id, action_taken, "timestamp" AS created_at '
                'FROM system_logs ORDER BY "timestamp" DESC LIMIT %s',
                (safe_limit,),
            ).fetchall()
        return [
            {"id": row["id"], "action": row["action_taken"], "time": row["created_at"].isoformat()}
            for row in rows
        ]

    if MYSQL_ENABLED:
        with mysql_db() as con:
            with con.cursor() as cursor:
                cursor.execute(
                    "SELECT log_id AS id, action_taken, timestamp AS created_at FROM system_logs ORDER BY timestamp DESC LIMIT %s",
                    (safe_limit,),
                )
                rows = cursor.fetchall()
        return [{
            "id": row["id"], "action": row["action_taken"],
            "time": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        } for row in rows]

    with db() as con:
        rows = con.execute(
            "SELECT id,action_taken,created_at FROM system_logs ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return [{"id": row["id"], "action": row["action_taken"], "time": row["created_at"]} for row in rows]

@app.on_event("startup")
def startup():
    init_db()

def require_admin(authorization: Optional[str]):
    if not SUPER_ADMIN_TOKEN and not any(account["token"] for account in BOOTSTRAP_ADMIN_TOKENS):
        raise HTTPException(500, "Configure SUPER_ADMIN_TOKEN and administrator tokens in server/.env.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Administrator authentication required.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Administrator authentication required.")
    if SUPER_ADMIN_TOKEN and hmac.compare_digest(token, SUPER_ADMIN_TOKEN):
        return {
            "id": None,
            "name": "Programmer",
            "role": "super_admin",
            "organization": "all",
            "organization_label": "Super Admin",
        }

    hashed_token = token_hash(token)
    if PG_ENABLED:
        with pg_db() as con:
            account = con.execute(
                "SELECT id,name,organization,organization_name,token_hash,active,deleted FROM admin_accounts WHERE token_hash=%s LIMIT 1",
                (hashed_token,),
            ).fetchone()
    elif MYSQL_ENABLED:
        with mysql_db() as con:
            with con.cursor() as cursor:
                cursor.execute(
                    "SELECT id,name,organization,organization_name,token_hash,active,deleted FROM admin_accounts WHERE token_hash=%s LIMIT 1",
                    (hashed_token,),
                )
                account = cursor.fetchone()
    else:
        with db() as con:
            account = con.execute(
                "SELECT id,name,organization,organization_name,token_hash,active,deleted FROM admin_accounts WHERE token_hash=? LIMIT 1",
                (hashed_token,),
            ).fetchone()

    if not account or not hmac.compare_digest(account["token_hash"], hashed_token):
        raise HTTPException(401, "Administrator token is invalid.")
    if not account["active"] or account["deleted"]:
        raise HTTPException(403, "This administrator account is restricted or deleted.")
    return {
        "id": account["id"],
        "name": account["name"],
        "role": "admin",
        "organization": account["organization"],
        "organization_label": organization_label(account["organization"], account["organization_name"]),
    }

def require_super_admin(authorization: Optional[str]):
    principal = require_admin(authorization)
    if principal["role"] != "super_admin":
        raise HTTPException(403, "Only the super administrator can manage admin accounts.")
    return principal

def report_scope(principal, latitude_column: str = "latitude", longitude_column: str = "longitude"):
    if principal["organization"] == "cityhall_bacoor":
        min_lat, max_lat, min_lng, max_lng = BACOOR_BOUNDS
        return (
            f"{latitude_column} BETWEEN %s AND %s AND {longitude_column} BETWEEN %s AND %s",
            (min_lat, max_lat, min_lng, max_lng),
        )
    return "1=1", ()

def organization_label(organization, organization_name=None):
    if organization == "mdrrmo":
        return "MDRRMO"
    if organization == "cityhall_bacoor":
        return "Bacoor City Hall"
    if organization == "other_lgu":
        return f"Other City Hall / LGU: {organization_name}"
    if organization == "other_org":
        return organization_name or "Other Organization"
    return organization.replace("_", " ").title()

def admin_account_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "organization": row["organization"],
        "organization_label": organization_label(row["organization"], row["organization_name"]),
        "organization_name": row["organization_name"],
        "role": "admin",
        "active": bool(row["active"]),
        "created_at": row["created_at"],
    }

ACCOUNT_COLUMNS = "id,name,organization,organization_name,active,created_at"

def pg_admin_json(row):
    item = admin_account_json(row)
    item["created_at"] = str(row["created_at"])
    return item

@app.get("/api/admin/accounts")
def list_admin_accounts(authorization: Optional[str] = Header(default=None)):
    require_super_admin(authorization)
    with pg_db() as con:
        rows = con.execute(
            f"SELECT {ACCOUNT_COLUMNS} FROM admin_accounts WHERE deleted=FALSE ORDER BY id"
        ).fetchall()
    return {"items": [pg_admin_json(r) for r in rows]}

@app.post("/api/admin/accounts", status_code=201)
def create_admin_account(
    payload: AdminAccountCreate,
    authorization: Optional[str] = Header(default=None),
):
    require_super_admin(authorization)
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Admin name cannot be blank.")
    organization_name = payload.organization_name.strip() if payload.organization_name else ""
    if payload.organization in {"other_lgu", "other_org"} and not organization_name:
        raise HTTPException(422, "Enter the city, municipality, or organization name.")
    organization_name = organization_name or None
    token = secrets.token_urlsafe(32)
    account_key = f"managed:{uuid4().hex}"
    with pg_db() as con:
        row = con.execute(
            "INSERT INTO admin_accounts(account_key,name,organization,organization_name,token_hash) "
            f"VALUES(%s,%s,%s,%s,%s) RETURNING {ACCOUNT_COLUMNS}",
            (account_key, name, payload.organization, organization_name, token_hash(token)),
        ).fetchone()
    return {"account": pg_admin_json(row), "token": token}

@app.patch("/api/admin/accounts/{account_id}")
def update_admin_account(
    account_id: int,
    payload: AdminAccountUpdate,
    authorization: Optional[str] = Header(default=None),
):
    require_super_admin(authorization)
    with pg_db() as con:
        row = con.execute(
            f"UPDATE admin_accounts SET active=%s WHERE id=%s AND deleted=FALSE RETURNING {ACCOUNT_COLUMNS}",
            (payload.active, account_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Admin account not found.")
    return {"account": pg_admin_json(row)}

@app.delete("/api/admin/accounts/{account_id}")
def delete_admin_account(
    account_id: int,
    authorization: Optional[str] = Header(default=None),
):
    require_super_admin(authorization)
    with pg_db() as con:
        cur = con.execute(
            "UPDATE admin_accounts SET active=FALSE,deleted=TRUE WHERE id=%s AND deleted=FALSE",
            (account_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Admin account not found.")
    return {"deleted": True, "id": account_id}

def hazard_json(row):
    return {
        "id": str(row["id"]),
        "type": row["type"],
        "description": row["description"],
        "time": row["created_at"],
        "status": row["status"],
        "lat": row["lat"],
        "lng": row["lng"],
        "photo_url": row["photo_url"],
    }

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "resqlink-python-api",
        "version": app.version,
        "database": "postgres" if PG_ENABLED else ("mysql" if MYSQL_ENABLED else "sqlite"),
    }

def announcement_json(row):
    return {
        "id": row["alert_id"],
        "title": row["title"],
        "message": row["message"],
        "level": row["alert_level"],
        "audience": row["target_area"] or "all",
        "created_at": str(row["created_at"]),
    }

def contact_json(row):
    return {
        "id": row["contact_id"],
        "name": row["contact_name"],
        "phone": row["contact_phone"],
        "relationship": row["relationship"] or "Emergency contact",
    }

@app.get("/api/announcements")
def get_announcements():
    with pg_db() as con:
        rows = con.execute(
            "SELECT * FROM alerts_announcements ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return {"items": [announcement_json(r) for r in rows]}

@app.post("/api/announcements", status_code=201)
def create_announcement(
    payload: AnnouncementPayload,
    authorization: Optional[str] = Header(default=None),
):
    require_admin(authorization)
    with pg_db() as con:
        admin_id = pg_guest_user_id(con)
        row = con.execute(
            "INSERT INTO alerts_announcements(admin_id,title,message,target_area,alert_level) "
            "VALUES(%s,%s,%s,%s,%s) RETURNING *",
            (admin_id, payload.title.strip(), payload.message.strip(),
             payload.audience.strip() or "all", payload.level.strip() or "info"),
        ).fetchone()
    return {"item": announcement_json(row)}

@app.get("/api/user/profile")
def get_user_profile():
    with pg_db() as con:
        row = con.execute(
            "SELECT full_name, phone_number FROM users WHERE email=%s LIMIT 1",
            ("guest@example.com",),
        ).fetchone()
    return {
        "full_name": row["full_name"] if row else "Guest User",
        "phone_number": row["phone_number"] if row else "09000000000",
        "home_address": "Bacoor, Cavite",
    }

@app.put("/api/user/profile")
def update_user_profile(payload: UserProfilePayload):
    with pg_db() as con:
        pg_guest_user_id(con)  # makes sure the guest row exists
        con.execute(
            "UPDATE users SET full_name=%s, phone_number=%s WHERE email=%s",
            (payload.full_name.strip(), payload.phone_number or "09000000000", "guest@example.com"),
        )
    return {"ok": True, "profile": {
        "full_name": payload.full_name.strip(),
        "phone_number": payload.phone_number or "09000000000",
        "home_address": payload.home_address or "Bacoor, Cavite",
    }}

@app.get("/api/emergency-contacts")
def get_emergency_contacts():
    with pg_db() as con:
        rows = con.execute(
            "SELECT * FROM emergency_contacts ORDER BY contact_id DESC LIMIT 10"
        ).fetchall()
    return {"items": [contact_json(r) for r in rows]}

@app.post("/api/emergency-contacts", status_code=201)
def create_emergency_contact(payload: EmergencyContactPayload):
    with pg_db() as con:
        user_id = pg_guest_user_id(con)
        row = con.execute(
            "INSERT INTO emergency_contacts(user_id,contact_name,contact_phone,relationship) "
            "VALUES(%s,%s,%s,%s) RETURNING *",
            (user_id, payload.contact_name.strip(), payload.contact_phone.strip(),
             payload.relationship.strip() if payload.relationship else "Emergency contact"),
        ).fetchone()
    return {"item": contact_json(row)}

@app.post("/api/sos/medical", status_code=201)
def start_medical_sos(payload: SosCreate):
    payload.label = payload.label or "Medical / Ambulance assistance"
    if not payload.label:
        payload.label = "Medical / Ambulance assistance"
    return start_sos(payload)

@app.get("/api/hazards")
def get_hazards():
    with pg_db() as con:
        rows = con.execute(
            "SELECT * FROM disaster_reports ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return {"items": [mysql_report_json(r) for r in rows]}

@app.post("/api/hazards", status_code=201)
def create_hazard(payload: HazardCreate):
    with pg_db() as con:
        user_id = pg_guest_user_id(con)
        row = con.execute(
            "INSERT INTO disaster_reports(user_id,hazard_type,description,latitude,longitude,status,severity_level) "
            "VALUES(%s,%s,%s,%s,%s,'pending',3) RETURNING *",
            (user_id, normalize_hazard_type(payload.type), payload.description.strip(), payload.lat, payload.lng),
        ).fetchone()
    log_event(f"Incident report submitted: {payload.type.strip()}")
    return {"item": mysql_report_json(row)}

@app.post("/api/reports", status_code=201)
async def create_report(
    type: str = Form(..., min_length=1, max_length=80),
    description: str = Form(..., min_length=10, max_length=280),
    lat: float = Form(...),
    lng: float = Form(...),
    image: Optional[UploadFile] = File(default=None),
):
    photo_url = None
    public_id = None
    if image is not None:
        extension = ALLOWED_IMAGE_TYPES.get(image.content_type or "")
        if extension is None:
            raise HTTPException(415, "Upload a JPG, PNG, or WEBP image.")
        content = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "The photo must be 8 MB or smaller.")
        uploaded = await run_in_threadpool(upload_photo, content)
        photo_url = uploaded["url"]
        public_id = uploaded["public_id"]

    try:
        with pg_db() as con:
            user_id = pg_guest_user_id(con)
            row = con.execute(
                "INSERT INTO disaster_reports(user_id,hazard_type,description,latitude,longitude,image_url,status,severity_level) "
                "VALUES(%s,%s,%s,%s,%s,%s,'pending',3) RETURNING *",
                (user_id, normalize_hazard_type(type), description.strip(), lat, lng, photo_url),
            ).fetchone()
    except Exception:
        delete_photo(public_id)
        raise

    log_event(f"Incident report with photo submitted: {type.strip()}" if photo_url else f"Incident report submitted: {type.strip()}")
    return {"item": mysql_report_json(row)}

@app.post("/api/reports/json", status_code=201)
def create_report_json(payload: ReportPayload):
    photo_url = None
    public_id = None
    if payload.image_base64:
        mime_type = payload.image_mime or "image/jpeg"
        extension = ALLOWED_IMAGE_TYPES.get(mime_type)
        if extension is None:
            raise HTTPException(415, "Upload a JPG, PNG, or WEBP image.")
        if len(payload.image_base64) > 12 * 1024 * 1024:
            raise HTTPException(413, "The photo must be 8 MB or smaller.")
        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "The photo data is invalid.")
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "The photo must be 8 MB or smaller.")
        uploaded = upload_photo(image_bytes)
        photo_url = uploaded["url"]
        public_id = uploaded["public_id"]

    try:
        with pg_db() as con:
            user_id = pg_guest_user_id(con)
            row = con.execute(
                "INSERT INTO disaster_reports(user_id,hazard_type,description,latitude,longitude,image_url,status,severity_level) "
                "VALUES(%s,%s,%s,%s,%s,%s,'pending',3) RETURNING *",
                (user_id, normalize_hazard_type(payload.type), payload.description.strip(), payload.lat, payload.lng, photo_url),
            ).fetchone()
    except Exception:
        delete_photo(public_id)
        raise

    log_event(f"Incident report submitted: {payload.type.strip()}")
    return {"item": mysql_report_json(row)}

@app.get("/api/sos/status")
def sos_status():
    with pg_db() as con:
        row = con.execute(
            "SELECT * FROM sos_alerts WHERE status='active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return {"active": False, "item": None}
    return {"active": True, "item": {
        "id": row["sos_id"], "lat": float(row["latitude"]), "lng": float(row["longitude"]),
        "label": "Current phone location", "active": True, "created_at": str(row["created_at"]),
    }}

@app.post("/api/sos", status_code=201)
def start_sos(payload: SosCreate):
    with pg_db() as con:
        user_id = pg_guest_user_id(con)
        con.execute(
            "UPDATE sos_alerts SET status='resolved' WHERE status='active' AND user_id=%s",
            (user_id,),
        )
        row = con.execute(
            "INSERT INTO sos_alerts(user_id,latitude,longitude,status) "
            "VALUES(%s,%s,%s,'active') RETURNING sos_id",
            (user_id, payload.lat, payload.lng),
        ).fetchone()
    log_event("SOS started")
    return {"active": True, "item": {
        "id": row["sos_id"], "lat": payload.lat, "lng": payload.lng,
        "label": payload.label.strip(), "active": True,
    }}

@app.delete("/api/sos")
def stop_sos():
    with pg_db() as con:
        user_id = pg_guest_user_id(con)
        con.execute(
            "UPDATE sos_alerts SET status='resolved' WHERE status='active' AND user_id=%s",
            (user_id,),
        )
    log_event("SOS stopped")
    return {"active": False}

@app.get("/api/logs")
def list_system_logs(limit: int = 100):
    return {"items": get_logs(limit)}

@app.get("/api/agencies")
def get_agencies(type: Optional[str] = None, lat: Optional[float] = None, lng: Optional[float] = None):
    query = "SELECT * FROM emergency_agencies"
    params = ()
    if type:
        query += " WHERE agency_type=%s"
        params = (type.strip().lower(),)
    query += " ORDER BY name LIMIT 100"
    with pg_db() as con:
        rows = con.execute(query, params).fetchall()

    items = [{
        "id": r["agency_id"], "type": r["agency_type"], "name": r["name"],
        "address": r["address"], "hotline": r["hotline"],
        "alternate_phone": r["alternate_phone"],
        "lat": r["latitude"], "lng": r["longitude"],
    } for r in rows if r["latitude"] is not None and r["longitude"] is not None]
    if lat is not None and lng is not None:
        for item in items:
            item["distance_km"] = haversine_km(lat, lng, item["lat"], item["lng"])
        items.sort(key=lambda item: item["distance_km"])
    return {"items": items}

def evacuation_center_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "capacity": row["capacity"] or 0,
        "occupancy": row["current_occupancy"] or 0,
        "status": row["status"],
    }

def validate_center_payload(payload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Evacuation center name cannot be blank.")
    if payload.occupancy > payload.capacity:
        raise HTTPException(422, "Occupancy cannot exceed the center's capacity.")
    return name, payload.address.strip() if payload.address else None

CENTER_COLUMNS = "shelter_id AS id,name,address,latitude,longitude,capacity,current_occupancy,status"

@app.get("/api/centers")
def list_evacuation_centers(
    page: int = 1,
    search: str = "",
    authorization: Optional[str] = Header(default=None),
):
    require_admin(authorization)
    if page < 1:
        raise HTTPException(422, "Page must be greater than zero.")
    search_term = f"%{search.strip()}%"
    offset = (page - 1) * 20
    with pg_db() as con:
        total = con.execute(
            "SELECT COUNT(*) AS total FROM shelters WHERE name ILIKE %s OR COALESCE(address,'') ILIKE %s",
            (search_term, search_term),
        ).fetchone()["total"]
        rows = con.execute(
            f"SELECT {CENTER_COLUMNS} FROM shelters "
            "WHERE name ILIKE %s OR COALESCE(address,'') ILIKE %s "
            "ORDER BY name LIMIT 20 OFFSET %s",
            (search_term, search_term, offset),
        ).fetchall()
    return {"rows": [evacuation_center_json(r) for r in rows], "total": total, "page": page}

@app.post("/api/centers", status_code=201)
def create_evacuation_center(
    payload: EvacuationCenterPayload,
    authorization: Optional[str] = Header(default=None),
):
    require_admin(authorization)
    name, address = validate_center_payload(payload)
    with pg_db() as con:
        row = con.execute(
            "INSERT INTO shelters(name,address,latitude,longitude,capacity,current_occupancy,status) "
            f"VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING {CENTER_COLUMNS}",
            (name, address, payload.latitude, payload.longitude, payload.capacity, payload.occupancy, payload.status),
        ).fetchone()
    return {"item": evacuation_center_json(row)}

@app.patch("/api/centers/{center_id}")
def update_evacuation_center(
    center_id: int,
    payload: EvacuationCenterPayload,
    authorization: Optional[str] = Header(default=None),
):
    require_admin(authorization)
    name, address = validate_center_payload(payload)
    with pg_db() as con:
        row = con.execute(
            "UPDATE shelters SET name=%s,address=%s,latitude=%s,longitude=%s,"
            "capacity=%s,current_occupancy=%s,status=%s WHERE shelter_id=%s "
            f"RETURNING {CENTER_COLUMNS}",
            (name, address, payload.latitude, payload.longitude, payload.capacity, payload.occupancy, payload.status, center_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Evacuation center not found.")
    return {"item": evacuation_center_json(row)}

@app.delete("/api/centers/{center_id}")
def delete_evacuation_center(center_id: int, authorization: Optional[str] = Header(default=None)):
    require_admin(authorization)
    with pg_db() as con:
        cur = con.execute("DELETE FROM shelters WHERE shelter_id=%s", (center_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Evacuation center not found.")
    return {"deleted": True}

@app.get("/api/shelters")
def get_shelters(lat: Optional[float] = None, lng: Optional[float] = None):
    with pg_db() as con:
        rows = con.execute(
            f"SELECT {CENTER_COLUMNS} FROM shelters WHERE status='open' ORDER BY name LIMIT 100"
        ).fetchall()
    items = [{
        "id": r["id"], "type": "Evacuation Center", "kind": "Evacuation Center",
        "description": r["name"], "address": r["address"], "status": r["status"],
        "lat": float(r["latitude"]), "lng": float(r["longitude"]),
        "capacity": r["capacity"], "current_occupancy": r["current_occupancy"],
    } for r in rows]
    if lat is not None and lng is not None:
        for item in items:
            item["distance_km"] = haversine_km(lat, lng, item["lat"], item["lng"])
        items.sort(key=lambda item: item["distance_km"])
    return {"items": items}

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt

    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    value = sin(delta_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lng / 2) ** 2
    return 6371 * 2 * atan2(sqrt(value), sqrt(1 - value))

@app.get("/api/admin/overview")
def admin_overview(authorization: Optional[str] = Header(default=None)):
    principal = require_admin(authorization)
    scope, params = report_scope(principal)
    with pg_db() as con:
        total = con.execute(
            f"SELECT COUNT(*) AS total FROM disaster_reports WHERE {scope}", params
        ).fetchone()["total"]
        pending = con.execute(
            f"SELECT COUNT(*) AS total FROM disaster_reports WHERE status='pending' AND {scope}", params
        ).fetchone()["total"]
        verified = con.execute(
            f"SELECT COUNT(*) AS total FROM disaster_reports WHERE status='verified' AND {scope}", params
        ).fetchone()["total"]
        sos = con.execute(
            f"SELECT * FROM sos_alerts WHERE status='active' AND {scope} ORDER BY created_at DESC LIMIT 1",
            params,
        ).fetchone()
        rows = con.execute(
            f"SELECT * FROM disaster_reports WHERE {scope} ORDER BY created_at DESC LIMIT 100",
            params,
        ).fetchall()
    return {
        "userAccess": "authenticated",
        "principal": principal,
        "stats": {
            "totalReports": total,
            "pendingReports": pending,
            "verifiedReports": verified,
            "activeSos": sos is not None,
        },
        "hazards": [mysql_report_json(row) for row in rows],
        "activeSos": (
            {"id": sos["sos_id"], "lat": float(sos["latitude"]), "lng": float(sos["longitude"]), "active": True}
            if sos else None
        ),
    }

@app.put("/api/admin/hazards/{hazard_id}/verify")
def verify_hazard(hazard_id: int, authorization: Optional[str] = Header(default=None)):
    principal = require_admin(authorization)
    scope, params = report_scope(principal)
    with pg_db() as con:
        cur = con.execute(
            f"UPDATE disaster_reports SET status='verified' WHERE report_id=%s AND {scope}",
            (hazard_id, *params),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Incident report not found.")
        row = con.execute(
            "SELECT * FROM disaster_reports WHERE report_id=%s", (hazard_id,)
        ).fetchone()
    return {"item": mysql_report_json(row)}

@app.delete("/api/admin/hazards/{hazard_id}")
def delete_hazard(hazard_id: int, authorization: Optional[str] = Header(default=None)):
    principal = require_admin(authorization)
    scope, params = report_scope(principal)
    with pg_db() as con:
        cur = con.execute(
            f"DELETE FROM disaster_reports WHERE report_id=%s AND {scope}",
            (hazard_id, *params),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Incident report not found.")
    return {"deleted": True, "id": str(hazard_id)}

@app.post("/api/admin/sos/clear")
def clear_sos(authorization: Optional[str] = Header(default=None)):
    principal = require_admin(authorization)
    scope, params = report_scope(principal)
    with pg_db() as con:
        con.execute(
            f"UPDATE sos_alerts SET status='resolved' WHERE status='active' AND {scope}",
            params,
        )
    return {"active": False}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
