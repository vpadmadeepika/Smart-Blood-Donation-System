"""
Database Initialization, Helper Functions, and Demonstration Seed Data.
Smart Blood Donation Management System
"""

import os
import sqlite3
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'blood_donation.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db():
    """Returns a SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(force_reseed=False):
    """Initializes the database schema and seeds demo data if empty or forced."""
    conn = get_db()
    cursor = conn.cursor()
    
    if force_reseed:
        tables = [
            'request_status_history', 'notifications', 'appointments', 
            'inventory_transactions', 'blood_inventory', 'donor_matches', 
            'blood_requests', 'healthcare_organizations', 'recipient_profiles', 
            'donor_profiles', 'users'
        ]
        for t in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()

    with open(SCHEMA_PATH, 'r') as f:
        cursor.executescript(f.read())
    conn.commit()
    
    # Check if users table is populated
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    
    if count == 0 or force_reseed:
        seed_demo_data(conn)
        
    conn.close()

def seed_demo_data(conn):
    """Populates realistic, fictional demonstration records for all roles."""
    cursor = conn.cursor()
    
    # Clear existing data in reverse order of foreign keys if reseeding
    tables = [
        'request_status_history', 'notifications', 'appointments', 
        'inventory_transactions', 'blood_inventory', 'donor_matches', 
        'blood_requests', 'healthcare_organizations', 'recipient_profiles', 
        'donor_profiles', 'users'
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
    
    today = date.today()
    
    # -------------------------------------------------------------
    # 1. SEED USERS & ROLES
    # -------------------------------------------------------------
    users_to_seed = [
        # Admin
        ('admin', 'admin@bloodcare.org', generate_password_hash('admin123'), 'admin', 'Dr. Evelyn Reed (Admin)', '+1 (555) 019-2830'),
        
        # Blood Banks
        ('central_bank', 'central.bank@metroblood.org', generate_password_hash('bank123'), 'blood_bank', 'Central Red Cross Blood Center', '+1 (555) 012-4001'),
        ('city_lifeline', 'city.lifeline@bloodbank.org', generate_password_hash('bank123'), 'blood_bank', 'City LifeLine Blood Services', '+1 (555) 012-4002'),
        
        # Hospitals
        ('stmary_er', 'stmary.er@hospital.org', generate_password_hash('hospital123'), 'hospital', 'St. Mary Memorial Hospital', '+1 (555) 013-5001'),
        ('metro_general', 'metropolitan.er@hospital.org', generate_password_hash('hospital123'), 'hospital', 'Metropolitan General Trauma Center', '+1 (555) 013-5002'),
        
        # NGOs (Community Blood Drives & Awareness)
        ('hope_life_ngo', 'hope.life@ngo.org', generate_password_hash('ngo123'), 'ngo', 'Hope & Life Blood Awareness Foundation', '+1 (555) 016-8001'),
        
        # Recipients
        ('sarah_jenkins', 'sarah.jenkins@example.com', generate_password_hash('recipient123'), 'recipient', 'Sarah Jenkins', '+1 (555) 014-6001'),
        ('david_miller', 'david.miller@example.com', generate_password_hash('recipient123'), 'recipient', 'David Miller', '+1 (555) 014-6002'),
        
        # Donors (All 8 Blood Groups)
        ('alex_rivera', 'alex.donor@example.com', generate_password_hash('donor123'), 'donor', 'Alex Rivera', '+1 (555) 015-7001'), # O-
        ('priya_patel', 'priya.patel@example.com', generate_password_hash('donor123'), 'donor', 'Priya Patel', '+1 (555) 015-7002'), # A+
        ('marcus_chen', 'marcus.chen@example.com', generate_password_hash('donor123'), 'donor', 'Marcus Chen', '+1 (555) 015-7003'), # B+
        ('elena_rostova', 'elena.rostova@example.com', generate_password_hash('donor123'), 'donor', 'Elena Rostova', '+1 (555) 015-7004'), # AB+
        ('james_wilson', 'james.wilson@example.com', generate_password_hash('donor123'), 'donor', 'James Wilson', '+1 (555) 015-7005'), # O+
        ('maya_lin', 'maya.lin@example.com', generate_password_hash('donor123'), 'donor', 'Maya Lin', '+1 (555) 015-7006'), # A-
        ('samuel_green', 'samuel.green@example.com', generate_password_hash('donor123'), 'donor', 'Samuel Green', '+1 (555) 015-7007'), # B-
        ('ananya_sharma', 'ananya.sharma@example.com', generate_password_hash('donor123'), 'donor', 'Ananya Sharma', '+1 (555) 015-7008'), # AB-
    ]
    
    user_ids = {}
    for uname, email, pw_hash, role, fname, phone in users_to_seed:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name, phone) VALUES (?, ?, ?, ?, ?, ?)",
            (uname, email, pw_hash, role, fname, phone)
        )
        user_ids[uname] = cursor.lastrowid
        
    # -------------------------------------------------------------
    # 2. SEED HEALTHCARE ORGANIZATIONS
    # -------------------------------------------------------------
    orgs = [
        (user_ids['central_bank'], 'Central Red Cross Blood Center', 'blood_bank', 'BB-LIC-2024-884', 'Dr. Arthur Vance', '+1 (555) 012-4001', '100 Medical Plaza Way, Suite 400', 'Metro City', 'Medical District', 40.7180, -73.9980, '24/7 Service'),
        (user_ids['city_lifeline'], 'City LifeLine Blood Services', 'blood_bank', 'BB-LIC-2023-512', 'Nurse Coordinator Clara Bell', '+1 (555) 012-4002', '450 Civic Center Blvd', 'Metro City', 'Downtown', 40.7128, -74.0060, '08:00 AM - 08:00 PM'),
        (user_ids['stmary_er'], 'St. Mary Memorial Hospital', 'hospital', 'HOSP-REG-9932', 'Dr. Rachel Hughes, Chief of Surgery', '+1 (555) 013-5001', '750 Healthcare Boulevard', 'Metro City', 'Medical District', 40.7180, -73.9980, '24/7 Emergency Center'),
        (user_ids['metro_general'], 'Metropolitan General Trauma Center', 'hospital', 'HOSP-REG-8810', 'Dr. Jonathan Blake, Trauma Director', '+1 (555) 013-5002', '1220 West Park Avenue', 'Metro City', 'Westside', 40.7250, -74.0150, '24/7 Level 1 Trauma'),
        (user_ids['hope_life_ngo'], 'Hope & Life Blood Awareness Foundation', 'ngo', 'NGO-REG-2024-110', 'Elena Cruz, Community Director', '+1 (555) 016-8001', '800 Community Drive, Tech Park', 'Metro City', 'Tech Park', 40.7500, -74.0050, '09:00 AM - 06:00 PM'),
    ]
    cursor.executemany(
        """INSERT INTO healthcare_organizations 
           (user_id, org_name, org_type, license_number, contact_person, emergency_helpline, address, city, area, latitude, longitude, operating_hours) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        orgs
    )
    
    # -------------------------------------------------------------
    # 3. SEED DONOR PROFILES
    # -------------------------------------------------------------
    donor_profiles_data = [
        (user_ids['alex_rivera'], 'O-', 29, 'Male', 'Metro City', 'Downtown', 40.7128, -74.0060, (today - timedelta(days=110)).strftime('%Y-%m-%d'), 1, 1, 'Healthy universal donor, regular volunteer.', 6),
        (user_ids['priya_patel'], 'A+', 26, 'Female', 'Metro City', 'Medical District', 40.7180, -73.9980, (today - timedelta(days=125)).strftime('%Y-%m-%d'), 1, 1, 'Platelet donor candidate.', 4),
        (user_ids['marcus_chen'], 'B+', 34, 'Male', 'Metro City', 'Westside', 40.7250, -74.0150, (today - timedelta(days=95)).strftime('%Y-%m-%d'), 1, 1, 'No chronic conditions.', 5),
        (user_ids['elena_rostova'], 'AB+', 28, 'Female', 'Metro City', 'North City', 40.7450, -73.9900, (today - timedelta(days=150)).strftime('%Y-%m-%d'), 1, 1, 'Universal plasma donor.', 3),
        (user_ids['james_wilson'], 'O+', 42, 'Male', 'Metro City', 'South District', 40.7000, -74.0100, (today - timedelta(days=40)).strftime('%Y-%m-%d'), 0, 1, 'Currently on recovery interval after recent donation.', 8),
        (user_ids['maya_lin'], 'A-', 31, 'Female', 'Metro City', 'East Hills', 40.7300, -73.9750, (today - timedelta(days=100)).strftime('%Y-%m-%d'), 1, 1, 'Rare Rh-negative advocate.', 4),
        (user_ids['samuel_green'], 'B-', 38, 'Male', 'Metro City', 'Tech Park', 40.7500, -74.0050, (today - timedelta(days=180)).strftime('%Y-%m-%d'), 1, 1, 'Corporate blood drive participant.', 2),
        (user_ids['ananya_sharma'], 'AB-', 24, 'Female', 'Metro City', 'Suburban Greens', 40.7600, -73.9600, (today - timedelta(days=210)).strftime('%Y-%m-%d'), 1, 1, 'College student donor.', 1),
    ]
    cursor.executemany(
        """INSERT INTO donor_profiles 
           (user_id, blood_group, age, gender, city, area, latitude, longitude, last_donation_date, is_available, consent_contact, medical_notes, total_donations) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        donor_profiles_data
    )
    
    # -------------------------------------------------------------
    # 4. SEED RECIPIENT PROFILES
    # -------------------------------------------------------------
    recipients_data = [
        (user_ids['sarah_jenkins'], 'Metro City', 'Downtown', '+1 (555) 014-9991', 'A+', 'Scheduled for orthopedic knee surgery.'),
        (user_ids['david_miller'], 'Metro City', 'East Hills', '+1 (555) 014-9992', 'O-', 'Family member ongoing therapy support.'),
    ]
    cursor.executemany(
        """INSERT INTO recipient_profiles (user_id, city, area, emergency_contact, blood_group_preference, notes) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        recipients_data
    )
    
    # -------------------------------------------------------------
    # 5. SEED BLOOD INVENTORY (Central & LifeLine Blood Banks)
    # -------------------------------------------------------------
    inventory_items = [
        # Central Red Cross Blood Center
        (user_ids['central_bank'], 'A+', 18, 'BATCH-2026-A101', (today - timedelta(days=10)).strftime('%Y-%m-%d'), (today + timedelta(days=25)).strftime('%Y-%m-%d'), 'Cold Room Shelf A-1', 'Available', 8),
        (user_ids['central_bank'], 'A-', 6, 'BATCH-2026-A102', (today - timedelta(days=5)).strftime('%Y-%m-%d'), (today + timedelta(days=30)).strftime('%Y-%m-%d'), 'Cold Room Shelf A-2', 'Available', 5),
        (user_ids['central_bank'], 'B+', 14, 'BATCH-2026-B201', (today - timedelta(days=12)).strftime('%Y-%m-%d'), (today + timedelta(days=23)).strftime('%Y-%m-%d'), 'Cold Room Shelf B-1', 'Available', 6),
        (user_ids['central_bank'], 'B-', 3, 'BATCH-2026-B202', (today - timedelta(days=28)).strftime('%Y-%m-%d'), (today + timedelta(days=7)).strftime('%Y-%m-%d'), 'Cold Room Shelf B-2', 'Low Stock', 5),
        (user_ids['central_bank'], 'AB+', 10, 'BATCH-2026-AB301', (today - timedelta(days=15)).strftime('%Y-%m-%d'), (today + timedelta(days=20)).strftime('%Y-%m-%d'), 'Cold Room Shelf C-1', 'Available', 4),
        (user_ids['central_bank'], 'AB-', 2, 'BATCH-2026-AB302', (today - timedelta(days=30)).strftime('%Y-%m-%d'), (today + timedelta(days=5)).strftime('%Y-%m-%d'), 'Cold Room Shelf C-2', 'Expiring Soon', 4),
        (user_ids['central_bank'], 'O+', 24, 'BATCH-2026-O401', (today - timedelta(days=8)).strftime('%Y-%m-%d'), (today + timedelta(days=27)).strftime('%Y-%m-%d'), 'Cold Room Shelf D-1', 'Available', 10),
        (user_ids['central_bank'], 'O-', 4, 'BATCH-2026-O402', (today - timedelta(days=14)).strftime('%Y-%m-%d'), (today + timedelta(days=21)).strftime('%Y-%m-%d'), 'Cold Room Shelf D-2', 'Low Stock', 8),
        
        # City LifeLine Blood Services
        (user_ids['city_lifeline'], 'A+', 12, 'LL-2026-081', (today - timedelta(days=7)).strftime('%Y-%m-%d'), (today + timedelta(days=28)).strftime('%Y-%m-%d'), 'Unit 1 Bay 3', 'Available', 6),
        (user_ids['city_lifeline'], 'B+', 9, 'LL-2026-082', (today - timedelta(days=9)).strftime('%Y-%m-%d'), (today + timedelta(days=26)).strftime('%Y-%m-%d'), 'Unit 1 Bay 4', 'Available', 5),
        (user_ids['city_lifeline'], 'O+', 15, 'LL-2026-083', (today - timedelta(days=11)).strftime('%Y-%m-%d'), (today + timedelta(days=24)).strftime('%Y-%m-%d'), 'Unit 2 Bay 1', 'Available', 8),
        (user_ids['city_lifeline'], 'O-', 2, 'LL-2026-084', (today - timedelta(days=32)).strftime('%Y-%m-%d'), (today + timedelta(days=3)).strftime('%Y-%m-%d'), 'Unit 2 Bay 2', 'Expiring Soon', 5),
    ]
    cursor.executemany(
        """INSERT INTO blood_inventory 
           (blood_bank_user_id, blood_group, units, batch_number, collection_date, expiry_date, storage_location, status, min_threshold) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        inventory_items
    )
    
    # -------------------------------------------------------------
    # 6. SEED INVENTORY TRANSACTIONS
    # -------------------------------------------------------------
    transactions = [
        (user_ids['central_bank'], 'O+', 'Collection', 10, 'BATCH-2026-O401', 'Routine drive collection at Tech Park', 'Dr. Arthur Vance'),
        (user_ids['central_bank'], 'A+', 'Collection', 8, 'BATCH-2026-A101', 'Walk-in voluntary donations', 'Nurse Clara'),
        (user_ids['central_bank'], 'O-', 'Issue', 2, 'BATCH-2026-O402', 'Issued to St. Mary Emergency Dept for trauma surgery', 'Dr. Arthur Vance'),
        (user_ids['city_lifeline'], 'O+', 'Collection', 15, 'LL-2026-083', 'Mobile donation van collection at Civic Center', 'Clara Bell'),
    ]
    cursor.executemany(
        """INSERT INTO inventory_transactions 
           (blood_bank_user_id, blood_group, transaction_type, units, batch_number, notes, recorded_by) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        transactions
    )
    
    # -------------------------------------------------------------
    # 7. SEED BLOOD REQUESTS
    # -------------------------------------------------------------
    req1_code = "REQ-2026-1001"
    cursor.execute(
        """INSERT INTO blood_requests 
           (request_code, requester_user_id, patient_name, blood_group, units_needed, urgency, hospital_name, hospital_address, city, area, latitude, longitude, required_date, required_time, contact_phone, medical_reason, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req1_code, user_ids['stmary_er'], 'Robert Hayes', 'O-', 3, 'Critical', 'St. Mary Memorial Hospital', '750 Healthcare Blvd', 'Metro City', 'Medical District', 40.7180, -73.9980, today.strftime('%Y-%m-%d'), 'Immediate / ASAP', '+1 (555) 013-5001', 'Emergency cardiac bypass requiring universal O- red cells.', 'Matching in Progress', (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'))
    )
    req1_id = cursor.lastrowid
    
    req2_code = "REQ-2026-1002"
    cursor.execute(
        """INSERT INTO blood_requests 
           (request_code, requester_user_id, patient_name, blood_group, units_needed, urgency, hospital_name, hospital_address, city, area, latitude, longitude, required_date, required_time, contact_phone, medical_reason, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req2_code, user_ids['sarah_jenkins'], 'Sarah Jenkins (Self)', 'A+', 2, 'High', 'Metropolitan General Hospital', '1220 West Park Avenue', 'Metro City', 'Westside', 40.7250, -74.0150, (today + timedelta(days=1)).strftime('%Y-%m-%d'), '10:00 AM', '+1 (555) 014-6001', 'Elective joint replacement surgery planned transfusion.', 'Donors Notified', (datetime.now() - timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S'))
    )
    req2_id = cursor.lastrowid

    req3_code = "REQ-2026-1003"
    cursor.execute(
        """INSERT INTO blood_requests 
           (request_code, requester_user_id, patient_name, blood_group, units_needed, urgency, hospital_name, hospital_address, city, area, latitude, longitude, required_date, required_time, contact_phone, medical_reason, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req3_code, user_ids['metro_general'], 'Emily Watson', 'B+', 2, 'Routine', 'Metropolitan General Hospital', '1220 West Park Avenue', 'Metro City', 'Westside', 40.7250, -74.0150, (today + timedelta(days=3)).strftime('%Y-%m-%d'), '02:00 PM', '+1 (555) 013-5002', 'Hematology treatment transfusion.', 'Submitted', (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S'))
    )
    req3_id = cursor.lastrowid

    req4_code = "REQ-2026-0988"
    cursor.execute(
        """INSERT INTO blood_requests 
           (request_code, requester_user_id, patient_name, blood_group, units_needed, urgency, hospital_name, hospital_address, city, area, latitude, longitude, required_date, required_time, contact_phone, medical_reason, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req4_code, user_ids['stmary_er'], 'Thomas Brown', 'A+', 4, 'High', 'St. Mary Memorial Hospital', '750 Healthcare Blvd', 'Metro City', 'Medical District', 40.7180, -73.9980, (today - timedelta(days=3)).strftime('%Y-%m-%d'), '11:00 AM', '+1 (555) 013-5001', 'Severe trauma transfusion following accident.', 'Fulfilled', (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'))
    )
    req4_id = cursor.lastrowid
    
    # -------------------------------------------------------------
    # 8. SEED DONOR MATCHES
    # -------------------------------------------------------------
    matches = [
        # Matches for Req 1 (O- Critical)
        (req1_id, user_ids['alex_rivera'], 95.0, 1.2, 'Pending', 'Automatic notification dispatched to universal donor Alex Rivera.'),
        
        # Matches for Req 2 (A+ High)
        (req2_id, user_ids['priya_patel'], 96.5, 1.8, 'Accepted', 'Donor Priya Patel responded: Ready for donation at hospital blood bank tomorrow at 09:30 AM.'),
        (req2_id, user_ids['alex_rivera'], 88.0, 2.5, 'Pending', 'Compatible universal donor notified as backup.'),
        
        # Matches for Req 4 (Fulfilled)
        (req4_id, user_ids['priya_patel'], 98.0, 1.0, 'Completed', 'Donation successfully completed and transfused.'),
    ]
    cursor.executemany(
        """INSERT INTO donor_matches (request_id, donor_user_id, compatibility_score, distance_km, status, response_notes) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        matches
    )
    
    # -------------------------------------------------------------
    # 9. SEED STATUS HISTORY
    # -------------------------------------------------------------
    status_histories = [
        (req1_id, None, 'Submitted', user_ids['stmary_er'], 'Emergency request entered by ER desk.'),
        (req1_id, 'Submitted', 'Matching in Progress', user_ids['stmary_er'], 'Automated matching engine executed.'),
        
        (req2_id, None, 'Submitted', user_ids['sarah_jenkins'], 'Request created by recipient.'),
        (req2_id, 'Submitted', 'Matching in Progress', user_ids['sarah_jenkins'], 'Finding nearby compatible donors.'),
        (req2_id, 'Matching in Progress', 'Donors Notified', user_ids['sarah_jenkins'], 'Dispatched in-app match alerts to 2 compatible donors.'),
        
        (req4_id, None, 'Submitted', user_ids['stmary_er'], 'Trauma emergency request initiated.'),
        (req4_id, 'Submitted', 'Donors Notified', user_ids['stmary_er'], 'Matched with registered donor.'),
        (req4_id, 'Donors Notified', 'Fulfilled', user_ids['stmary_er'], 'Units successfully collected and administered.'),
    ]
    cursor.executemany(
        """INSERT INTO request_status_history (request_id, old_status, new_status, changed_by_user_id, comments) 
           VALUES (?, ?, ?, ?, ?)""",
        status_histories
    )
    
    # -------------------------------------------------------------
    # 10. SEED APPOINTMENTS
    # -------------------------------------------------------------
    appts = [
        ('APT-2026-0501', user_ids['alex_rivera'], user_ids['central_bank'], (today + timedelta(days=2)).strftime('%Y-%m-%d'), '10:00 AM - 10:30 AM', 'Scheduled', 'Regular whole blood donation.', 'Slot reserved at Station 2.'),
        ('APT-2026-0502', user_ids['priya_patel'], user_ids['central_bank'], (today + timedelta(days=4)).strftime('%Y-%m-%d'), '02:00 PM - 02:30 PM', 'Scheduled', 'Platelet donation appointment.', 'Fasting guidelines provided.'),
        ('APT-2026-0480', user_ids['marcus_chen'], user_ids['city_lifeline'], (today - timedelta(days=20)).strftime('%Y-%m-%d'), '11:00 AM - 11:30 AM', 'Completed', 'Voluntary blood drive.', 'Donated 450ml whole blood successfully.'),
    ]
    cursor.executemany(
        """INSERT INTO appointments (appointment_code, donor_user_id, blood_bank_user_id, appointment_date, time_slot, status, donor_notes, staff_notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        appts
    )
    
    # -------------------------------------------------------------
    # 11. SEED IN-APP NOTIFICATIONS
    # -------------------------------------------------------------
    notifs = [
        (user_ids['alex_rivera'], 'Urgent Blood Match (O-)', 'An emergency request REQ-2026-1001 for O- blood was submitted by St. Mary Memorial Hospital in your area.', 'emergency', '/donor/dashboard', 0),
        (user_ids['priya_patel'], 'Donation Request Response Accepted', 'Your response to assist Sarah Jenkins (REQ-2026-1002) has been confirmed.', 'match', '/donor/dashboard', 0),
        (user_ids['central_bank'], 'Low Stock Warning: O-', 'O- red cell inventory is currently 4 units (below safety threshold of 8 units).', 'inventory', '/bloodbank/dashboard', 0),
        (user_ids['central_bank'], 'Near Expiry Alert: AB-', 'Batch BATCH-2026-AB302 (2 units) expires in 5 days. Consider prioritized clinical allocation.', 'inventory', '/bloodbank/dashboard', 0),
        (user_ids['sarah_jenkins'], 'Donor Match Found', 'Good news! Donor Priya Patel has accepted your blood request REQ-2026-1002.', 'request', '/recipient/dashboard', 0),
        (user_ids['stmary_er'], 'Critical Request Logged', 'Request REQ-2026-1001 is active with 1 potential donor notified.', 'request', '/hospital/dashboard', 1),
        (user_ids['admin'], 'System Alert: Low O- Reserves', 'City-wide O- reserves across participating centers are under 10 units.', 'system', '/admin/dashboard', 0),
    ]
    cursor.executemany(
        """INSERT INTO notifications (user_id, title, message, type, link, is_read) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        notifs
    )
    
    conn.commit()
    print("Database schema verified and fictional demonstration records seeded successfully.")

if __name__ == '__main__':
    init_db(force_reseed=True)
