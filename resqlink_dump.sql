-- TABLE: hazards
CREATE TABLE hazards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            created_at TEXT NOT NULL
        , photo_url TEXT);
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (1, 'Severe Flash Flooding', 'Heavy rainfall is causing rapid street flooding. Vehicles are advised to use an alternate route.', 'Community verified', 14.41, 120.945, '2026-10-07T15:51:15.655606+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (2, 'Demo check', 'Connection test from system validation', 'Pending verification', 14.41, 120.945, '2026-10-07T16:01:30.659470+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (4, 'Flooding', 'Street is flooding near the main highway and vehicles are struggling to pass.', 'Pending verification', 14.4465842, 121.0000008, '2026-10-07T17:28:21.487424+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (6, 'Flooding', 'Street is flooding near the main highway and vehicles are struggling to pass.', 'Pending verification', 14.4465909, 120.9999919, '2026-10-08T12:40:02.649819+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (7, 'Fire', 'Fire reported near my current location.', 'Pending verification', 14.4465909, 120.9999919, '2026-10-08T12:43:35.677095+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (8, 'Fire', 'Fire reported near my current location.', 'Pending verification', 14.4466008, 120.9999903, '2026-10-08T13:13:49.878352+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (14, 'Flooding', 'Street is flooding near the main highway and vehicles are struggling to pass.', 'Pending verification', 14.4465907, 120.9999841, '2026-10-21T06:07:43.566006+00:00', '');
INSERT INTO "hazards" ("id", "type", "description", "status", "lat", "lng", "created_at", "photo_url") VALUES (15, 'Fire', 'Big fire near las piñas', 'Pending verification', 14.4465907, 120.9999841, '2026-10-21T06:08:21.873121+00:00', '/uploads/cbf00084dacf48eaa31226b039140a1f.jpg');

