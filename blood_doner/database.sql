```sql
CREATE DATABASE IF NOT EXISTS blood_donor_db;
USE blood_donor_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(150) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;

-- Donors table
CREATE TABLE IF NOT EXISTS donors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(10) NOT NULL,
    last_donation_date DATE NULL,
    registered_on DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending'
) ENGINE=InnoDB;

-- Donation records table
CREATE TABLE IF NOT EXISTS donation_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    donation_date DATE NOT NULL,
    volume_ml INT NOT NULL,
    hemoglobin_level FLOAT NULL,
    status VARCHAR(50) DEFAULT 'Completed',
    CONSTRAINT fk_donation_records_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Blood stock table
CREATE TABLE IF NOT EXISTS blood_stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    blood_group VARCHAR(5) NOT NULL UNIQUE,
    units_available INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- Rejected donors table
CREATE TABLE IF NOT EXISTS rejected_donors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    rejection_reason VARCHAR(250) NOT NULL,
    rejection_date DATE NULL,
    CONSTRAINT fk_rejected_donors_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Donation schedule table
CREATE TABLE IF NOT EXISTS donation_schedule (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    scheduled_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'Scheduled',
    CONSTRAINT fk_donation_schedule_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Post-donation follow-up table
CREATE TABLE IF NOT EXISTS post_donation_followup (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    followup_date DATE NOT NULL,
    notes TEXT NULL,
    CONSTRAINT fk_post_donation_followup_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- Initialize blood groups
INSERT IGNORE INTO blood_stock (blood_group, units_available)
VALUES
    ('A+', 0),
    ('A-', 0),
    ('B+', 0),
    ('B-', 0),
    ('AB+', 0),
    ('AB-', 0),
    ('O+', 0),
    ('O-', 0);
```
