-- DEV ONLY sample data for ResQLink (converted from the MySQL schema.sql).
-- Run once, AFTER schema_postgres.sql:  psql "$DATABASE_URL" -f seed_dev_postgres.sql
-- Do NOT load this into a real/production database.
-- The password_hash values are placeholders copied from the original file, not real logins.

BEGIN;

INSERT INTO users (full_name, email, phone_number, password_hash, role) VALUES
('Guest Viewer', 'guest@example.com', '09000000000', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'guest'),
('Rion Caballero', 'rion@example.com', '09171234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'user'),
('John Paul Hizole', 'jp@example.com', '09181234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'user'),
('CDRRMO Admin Bacoor', 'admin@cdrrmo.bacoor.gov.ph', '0461234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'admin'),
('LGU Super Admin', 'superadmin@bacoor.gov.ph', '0469876543', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'super_admin')
ON CONFLICT (email) DO NOTHING;

INSERT INTO emergency_agencies (agency_type, name, address, hotline, alternate_phone, latitude, longitude) VALUES
('hospital', 'Bacoor Doctors Medical Center', 'Aguinaldo Hwy, Bacoor', '911', '(046) 417-1234', 14.4590, 120.9560),
('hospital', 'St. Dominic Medical Center', 'Aguinaldo Hwy, Talaba, Bacoor', '911', '(046) 477-8888', 14.4710, 120.9710),
('hospital', 'Bacoor Community Hospital', 'Panapaan, Bacoor', '911', '(046) 434-5678', 14.4380, 120.9640),
('police', 'Bacoor City Police Station', 'Gen. Aguinaldo Hwy, Poblacion, Bacoor', '117', '(046) 471-2345', 14.4595, 120.9555),
('police', 'Molino Police Substation', 'Molino Blvd, Bacoor', '117', '(046) 472-3456', 14.4320, 120.9810),
('fire', 'Bureau of Fire Protection - Bacoor', 'City Hall Compound, Bacoor', '911', '(046) 471-1111', 14.4600, 120.9560),
('fire', 'Molino Fire Substation', 'Molino IV, Bacoor', '911', '(046) 472-2222', 14.4310, 120.9820),
('cdrrmo', 'CDRRMO Bacoor', 'City Hall Compound, Bacoor', '(046) 123-4567', '0917-800-0000', 14.4601, 120.9561);

INSERT INTO emergency_contacts (user_id, contact_name, contact_phone, relationship) VALUES
(2, 'Maria Caballero', '09171112222', 'Mother'),
(2, 'Jose Caballero', '09173334444', 'Father'),
(3, 'Anna Hizole', '09182223333', 'Sister');

INSERT INTO disaster_reports (user_id, hazard_type, description, latitude, longitude, status, severity_level) VALUES
(2, 'flood', 'Knee-deep flood near Molino Blvd.', 14.4321, 120.9812, 'pending', 3),
(3, 'flood', 'Flood rising fast near SM Bacoor', 14.4456, 120.9756, 'verified', 4),
(2, 'fire', 'Electrical fire near Zapote bridge', 14.4612, 120.9876, 'verified', 5);

INSERT INTO shelters (name, latitude, longitude, capacity, current_occupancy, status) VALUES
('Bacoor National High School', 14.4500, 120.9700, 500, 120, 'open'),
('Molino Elementary School', 14.4300, 120.9800, 300, 300, 'full'),
('Zapote Covered Court', 14.4600, 120.9900, 200, 50, 'open');

INSERT INTO road_blocks (report_id, latitude, longitude, radius_affected_meters, is_active) VALUES
(1, 14.4321, 120.9812, 50, TRUE),
(2, 14.4456, 120.9756, 100, TRUE);

INSERT INTO faqs (category, question_pattern, intent_tag, official_answer) VALUES
('Document Requests', 'How to get a barangay clearance?', 'get_barangay_clearance', 'To get a barangay clearance, please go to your respective Barangay Hall and bring a valid ID and Cedula.'),
('Emergency', 'What is the emergency hotline?', 'emergency_hotline', 'You can call the CDRRMO Bacoor hotline at (046) 123-4567 or dial 911.'),
('Announcements', 'Are classes suspended today?', 'class_suspension', 'Please check the official Bacoor LGU Facebook page for the latest class suspension announcements.');

INSERT INTO sos_alerts (user_id, latitude, longitude, status) VALUES
(2, 14.4325, 120.9815, 'active'),
(3, 14.4460, 120.9760, 'responded');

COMMIT;
