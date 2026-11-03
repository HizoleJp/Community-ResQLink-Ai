-- ResQLink PostgreSQL schema (converted from the MySQL schema.sql).
-- Works on Neon, Supabase, Render Postgres, or local Postgres 14+.
-- Run once:  psql "$DATABASE_URL" -f schema_postgres.sql
--
-- What changed from MySQL:
--   AUTO_INCREMENT        -> GENERATED ALWAYS AS IDENTITY
--   ENUM(...)             -> text + CHECK (easier to change later than a Postgres ENUM type)
--   TIMESTAMP             -> timestamptz (stores timezone, so Manila vs UTC doesn't bite you)
--   DECIMAL(10,8) lat/lng -> double precision (the driver gives you plain floats, not Decimal objects)
--   TINYINT/BOOLEAN       -> boolean
--   USE / CREATE DATABASE -> removed (the host already gives you a database)
-- Also added: admin_accounts (app.py creates it at runtime), indexes, lat/lng range checks.

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    user_id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name      varchar(100) NOT NULL,
    email          varchar(100) NOT NULL UNIQUE,
    phone_number   varchar(20)  NOT NULL,
    password_hash  varchar(255) NOT NULL,
    role           text NOT NULL DEFAULT 'user'
                   CHECK (role IN ('guest', 'user', 'admin', 'super_admin')),
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Admin accounts for the city hall / MDRRMO website (token based, tokens are stored hashed).
CREATE TABLE IF NOT EXISTS admin_accounts (
    id                 integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_key        varchar(120) NOT NULL UNIQUE,
    name               varchar(120) NOT NULL,
    organization       varchar(60)  NOT NULL,
    organization_name  varchar(120),
    token_hash         char(64) NOT NULL UNIQUE,
    active             boolean NOT NULL DEFAULT TRUE,
    deleted            boolean NOT NULL DEFAULT FALSE,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS emergency_agencies (
    agency_id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agency_type      text NOT NULL
                     CHECK (agency_type IN ('hospital', 'police', 'fire', 'cdrrmo', 'other')),
    name             varchar(150) NOT NULL,
    address          varchar(255) NOT NULL,
    hotline          varchar(50)  NOT NULL,
    alternate_phone  varchar(50),
    latitude         double precision CHECK (latitude  BETWEEN -90  AND 90),
    longitude        double precision CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        integer NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    contact_name   varchar(100) NOT NULL,
    contact_phone  varchar(20)  NOT NULL,
    relationship   varchar(50)
);

CREATE TABLE IF NOT EXISTS disaster_reports (
    report_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         integer NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    hazard_type     text NOT NULL
                    CHECK (hazard_type IN ('flood', 'typhoon', 'fire', 'landslide', 'structural_damage', 'other')),
    description     text,
    latitude        double precision NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude       double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    image_url       varchar(255),
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'verified', 'rejected', 'resolved')),
    severity_level  smallint CHECK (severity_level BETWEEN 1 AND 5),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS report_verifications (
    verification_id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id          integer NOT NULL REFERENCES disaster_reports(report_id) ON DELETE CASCADE,
    verifying_user_id  integer NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    is_confirmed       boolean NOT NULL DEFAULT TRUE,
    created_at         timestamptz NOT NULL DEFAULT now(),
    -- one vote per person per report (the MySQL version allowed duplicates)
    UNIQUE (report_id, verifying_user_id)
);

CREATE TABLE IF NOT EXISTS alerts_announcements (
    alert_id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_id     integer NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title        varchar(150) NOT NULL,
    message      text NOT NULL,
    target_area  varchar(100),
    alert_level  text NOT NULL CHECK (alert_level IN ('info', 'warning', 'critical')),
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Evacuation centers. In the SQLite mode app.py calls this evacuation_centers,
-- in MySQL mode it calls it shelters. One table, one name: shelters.
CREATE TABLE IF NOT EXISTS shelters (
    shelter_id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name               varchar(150) NOT NULL,
    address            varchar(255),
    latitude           double precision NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude          double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    capacity           integer NOT NULL CHECK (capacity >= 0),
    current_occupancy  integer NOT NULL DEFAULT 0 CHECK (current_occupancy >= 0),
    status             text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'full', 'closed'))
);

CREATE TABLE IF NOT EXISTS road_blocks (
    block_id                integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id               integer REFERENCES disaster_reports(report_id) ON DELETE SET NULL,
    latitude                double precision NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude               double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    radius_affected_meters  integer NOT NULL CHECK (radius_affected_meters >= 0),
    is_active               boolean NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS faqs (
    faq_id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category          varchar(100) NOT NULL,
    question_pattern  text NOT NULL,
    intent_tag        varchar(100) NOT NULL,
    official_answer   text NOT NULL
);

CREATE TABLE IF NOT EXISTS public_services (
    service_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_name     varchar(150) NOT NULL,
    requirements     text,
    office_location  varchar(150),
    contact_info     varchar(100)
);

CREATE TABLE IF NOT EXISTS chat_logs (
    log_id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           integer REFERENCES users(user_id) ON DELETE SET NULL,
    user_query        text NOT NULL,
    bot_response      text NOT NULL,
    confidence_score  numeric(5, 4),
    "timestamp"       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sos_alerts (
    sos_id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     integer NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    latitude    double precision NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude   double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'responded', 'resolved')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_logs (
    log_id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       integer REFERENCES users(user_id) ON DELETE SET NULL,
    action_taken  varchar(255) NOT NULL,
    ip_address    varchar(45),
    "timestamp"   timestamptz NOT NULL DEFAULT now()
);

-- Indexes for the queries the app actually runs (filter by status, newest first, by user).
-- Postgres does NOT auto-index foreign keys, so the FK columns are listed here on purpose.
CREATE INDEX IF NOT EXISTS idx_reports_status_created ON disaster_reports (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_user           ON disaster_reports (user_id);
CREATE INDEX IF NOT EXISTS idx_sos_status_created     ON sos_alerts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sos_user               ON sos_alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_user          ON emergency_contacts (user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created         ON alerts_announcements (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agencies_type          ON emergency_agencies (agency_type);
CREATE INDEX IF NOT EXISTS idx_shelters_status        ON shelters (status);
CREATE INDEX IF NOT EXISTS idx_roadblocks_active      ON road_blocks (is_active) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_verifications_report   ON report_verifications (report_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_time         ON chat_logs ("timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_time       ON system_logs ("timestamp" DESC);

COMMIT;
