-- Smart Blood Donation Management System
-- SQLite Schema Definition

PRAGMA foreign_keys = ON;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL CHECK(role IN ('donor', 'recipient', 'hospital', 'ngo', 'blood_bank', 'admin')),
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(30),
    avatar_url VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'pending')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Donor Profiles Table
CREATE TABLE IF NOT EXISTS donor_profiles (
    user_id INTEGER PRIMARY KEY,
    blood_group VARCHAR(5) NOT NULL CHECK(blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    age INTEGER CHECK(age >= 18 AND age <= 65),
    gender VARCHAR(20),
    city VARCHAR(100) NOT NULL,
    area VARCHAR(100) NOT NULL,
    latitude REAL,
    longitude REAL,
    last_donation_date DATE,
    is_available INTEGER DEFAULT 1 CHECK(is_available IN (0, 1)),
    consent_contact INTEGER DEFAULT 1 CHECK(consent_contact IN (0, 1)),
    medical_notes TEXT,
    total_donations INTEGER DEFAULT 0,
    eligibility_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Recipient Profiles Table
CREATE TABLE IF NOT EXISTS recipient_profiles (
    user_id INTEGER PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    area VARCHAR(100) NOT NULL,
    emergency_contact VARCHAR(100),
    blood_group_preference VARCHAR(5),
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Healthcare Organizations & NGOs (Hospitals, Blood Banks & NGOs)
CREATE TABLE IF NOT EXISTS healthcare_organizations (
    user_id INTEGER PRIMARY KEY,
    org_name VARCHAR(200) NOT NULL,
    org_type VARCHAR(30) NOT NULL CHECK(org_type IN ('hospital', 'blood_bank', 'ngo')),
    license_number VARCHAR(100),
    contact_person VARCHAR(150),
    emergency_helpline VARCHAR(50),
    address TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    area VARCHAR(100) NOT NULL,
    latitude REAL,
    longitude REAL,
    operating_hours VARCHAR(100) DEFAULT '24/7 Emergency Service',
    verified INTEGER DEFAULT 1 CHECK(verified IN (0, 1)),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Blood Requests Table
CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_code VARCHAR(30) UNIQUE NOT NULL,
    requester_user_id INTEGER NOT NULL,
    patient_name VARCHAR(150) NOT NULL,
    blood_group VARCHAR(5) NOT NULL CHECK(blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    units_needed INTEGER NOT NULL CHECK(units_needed > 0),
    urgency VARCHAR(20) NOT NULL CHECK(urgency IN ('Critical', 'High', 'Routine')),
    hospital_name VARCHAR(200) NOT NULL,
    hospital_address TEXT,
    city VARCHAR(100) NOT NULL,
    area VARCHAR(100) NOT NULL,
    latitude REAL,
    longitude REAL,
    required_date DATE NOT NULL,
    required_time VARCHAR(20),
    contact_phone VARCHAR(50) NOT NULL,
    medical_reason TEXT,
    status VARCHAR(30) DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Matching in Progress', 'Donors Notified', 'Response Received', 'Fulfilled', 'Cancelled')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (requester_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Donor Matches Table
CREATE TABLE IF NOT EXISTS donor_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    donor_user_id INTEGER NOT NULL,
    compatibility_score REAL DEFAULT 100.0,
    distance_km REAL,
    status VARCHAR(30) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Accepted', 'Declined', 'Completed')),
    response_notes TEXT,
    matched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (donor_user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(request_id, donor_user_id)
);

-- Blood Inventory (for Blood Banks)
CREATE TABLE IF NOT EXISTS blood_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_bank_user_id INTEGER NOT NULL,
    blood_group VARCHAR(5) NOT NULL CHECK(blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    units INTEGER NOT NULL CHECK(units >= 0),
    batch_number VARCHAR(50),
    collection_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    storage_location VARCHAR(100) DEFAULT 'Main Refrigerator Unit A',
    status VARCHAR(30) DEFAULT 'Available' CHECK(status IN ('Available', 'Low Stock', 'Expiring Soon', 'Expired', 'Reserved')),
    min_threshold INTEGER DEFAULT 5,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (blood_bank_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Inventory Transactions (Audit Log for issues and collections)
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_bank_user_id INTEGER NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    transaction_type VARCHAR(30) NOT NULL CHECK(transaction_type IN ('Collection', 'Issue', 'Disposal', 'Adjustment')),
    units INTEGER NOT NULL CHECK(units > 0),
    reference_request_id INTEGER,
    batch_number VARCHAR(50),
    notes TEXT,
    recorded_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (blood_bank_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reference_request_id) REFERENCES blood_requests(id) ON DELETE SET NULL
);

-- Donation Appointments Table
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_code VARCHAR(30) UNIQUE NOT NULL,
    donor_user_id INTEGER NOT NULL,
    blood_bank_user_id INTEGER NOT NULL,
    appointment_date DATE NOT NULL,
    time_slot VARCHAR(50) NOT NULL,
    status VARCHAR(30) DEFAULT 'Scheduled' CHECK(status IN ('Scheduled', 'Completed', 'Cancelled', 'No-Show')),
    donor_notes TEXT,
    staff_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (blood_bank_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- In-App Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(30) DEFAULT 'system' CHECK(type IN ('request', 'match', 'appointment', 'inventory', 'system', 'emergency')),
    link VARCHAR(255),
    is_read INTEGER DEFAULT 0 CHECK(is_read IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Request Status History (Timeline tracking)
CREATE TABLE IF NOT EXISTS request_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    old_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    changed_by_user_id INTEGER,
    comments TEXT,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Indices for rapid lookup
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_donor_bg ON donor_profiles(blood_group, is_available);
CREATE INDEX IF NOT EXISTS idx_requests_status ON blood_requests(status, urgency);
CREATE INDEX IF NOT EXISTS idx_inventory_bg ON blood_inventory(blood_bank_user_id, blood_group);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
