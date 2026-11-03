-- OPTIONAL: PostGIS upgrade. Run AFTER schema_postgres.sql.
-- Neon and Supabase both support PostGIS. Plain Postgres needs the postgis package installed.
--
-- This keeps your latitude/longitude columns (so nothing in the app breaks) and adds a
-- computed "geog" column that Postgres fills in for you, plus a spatial index on it.

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE disaster_reports  ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED;
ALTER TABLE shelters          ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED;
ALTER TABLE emergency_agencies ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED;
ALTER TABLE sos_alerts        ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED;
ALTER TABLE road_blocks       ADD COLUMN IF NOT EXISTS geog geography(Point, 4326)
    GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED;

CREATE INDEX IF NOT EXISTS idx_reports_geog   ON disaster_reports   USING GIST (geog);
CREATE INDEX IF NOT EXISTS idx_shelters_geog  ON shelters           USING GIST (geog);
CREATE INDEX IF NOT EXISTS idx_agencies_geog  ON emergency_agencies USING GIST (geog);
CREATE INDEX IF NOT EXISTS idx_sos_geog       ON sos_alerts         USING GIST (geog);
CREATE INDEX IF NOT EXISTS idx_roadblocks_geog ON road_blocks       USING GIST (geog);

-- Example: 5 nearest OPEN shelters to a point (lng, lat), with distance in meters.
-- Replaces the haversine loop in app.py.
--   SELECT name, capacity - current_occupancy AS free_spots,
--          ST_Distance(geog, ST_SetSRID(ST_MakePoint(120.97, 14.45), 4326)::geography) AS meters
--   FROM shelters
--   WHERE status = 'open'
--   ORDER BY geog <-> ST_SetSRID(ST_MakePoint(120.97, 14.45), 4326)::geography
--   LIMIT 5;

-- Example: is a point inside any active road block's affected radius?
--   SELECT block_id FROM road_blocks
--   WHERE is_active
--     AND ST_DWithin(geog, ST_SetSRID(ST_MakePoint(120.9812, 14.4321), 4326)::geography, radius_affected_meters);
