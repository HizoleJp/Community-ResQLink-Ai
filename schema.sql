-- CommunityLink ResQLink AI MySQL schema and development seed data.
-- Import into MySQL 8+ using: mysql -u <user> -p < server/schema.sql

CREATE DATABASE IF NOT EXISTS resqlink_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE resqlink_db;

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('guest', 'user', 'admin', 'super_admin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emergency_agencies (
    agency_id INT AUTO_INCREMENT PRIMARY KEY,
    agency_type ENUM('hospital', 'police', 'fire', 'cdrrmo', 'other') NOT NULL,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    hotline VARCHAR(50) NOT NULL,
    alternate_phone VARCHAR(50),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    contact_name VARCHAR(100) NOT NULL,
    contact_phone VARCHAR(20) NOT NULL,
    relationship VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS disaster_reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    hazard_type ENUM('flood', 'typhoon', 'fire', 'landslide', 'structural_damage', 'other') NOT NULL,
    description TEXT,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    image_url VARCHAR(255),
    status ENUM('pending', 'verified', 'rejected', 'resolved') DEFAULT 'pending',
    severity_level INT CHECK (severity_level BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_verifications (
    verification_id INT AUTO_INCREMENT PRIMARY KEY,
    report_id INT NOT NULL,
    verifying_user_id INT NOT NULL,
    is_confirmed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES disaster_reports(report_id) ON DELETE CASCADE,
    FOREIGN KEY (verifying_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts_announcements (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    target_area VARCHAR(100),
    alert_level ENUM('info', 'warning', 'critical') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shelters (
    shelter_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    capacity INT NOT NULL,
    current_occupancy INT DEFAULT 0,
    status ENUM('open', 'full', 'closed') DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS road_blocks (
    block_id INT AUTO_INCREMENT PRIMARY KEY,
    report_id INT,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    radius_affected_meters INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (report_id) REFERENCES disaster_reports(report_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS faqs (
    faq_id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    question_pattern TEXT NOT NULL,
    intent_tag VARCHAR(100) NOT NULL,
    official_answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public_services (
    service_id INT AUTO_INCREMENT PRIMARY KEY,
    service_name VARCHAR(150) NOT NULL,
    requirements TEXT,
    office_location VARCHAR(150),
    contact_info VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS chat_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    user_query TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    confidence_score DECIMAL(5, 4),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sos_alerts (
    sos_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    status ENUM('active', 'responded', 'resolved') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action_taken VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

INSERT IGNORE INTO users (full_name, email, phone_number, password_hash, role) VALUES
('Guest Viewer', 'guest@example.com', '09000000000', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'guest'),
('Rion Caballero', 'rion@example.com', '09171234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'user'),
('John Paul Hizole', 'jp@example.com', '09181234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'user'),
('CDRRMO Admin Bacoor', 'admin@cdrrmo.bacoor.gov.ph', '0461234567', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'admin'),
('LGU Super Admin', 'superadmin@bacoor.gov.ph', '0469876543', '$2y$10$e0MYzXyjpJS7Pd0RVvHwHe1HlCS4bZJ18JuywdRz1Pq0wL1s1s1s1', 'super_admin');

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
