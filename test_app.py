"""
Automated Test Suite for Smart Blood Donation Management System
Validates matching algorithms, role authentication, requests, inventory FIFO and workflows.
"""

import unittest
from datetime import date, timedelta
from app import app, get_db
import database
from matching import (
    get_compatible_donor_groups, is_compatible, rank_donors_for_request,
    calculate_haversine_distance, evaluate_donation_cooldown
)

class SmartBloodDonationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        database.init_db(force_reseed=True)

    def setUp(self):
        self.client = app.test_client()

    def test_1_smart_matching_matrix(self):
        """Test ABO and Rh compatibility rules."""
        # O- is Universal Donor
        self.assertTrue(is_compatible('O-', 'AB+'))
        self.assertTrue(is_compatible('O-', 'O-'))
        self.assertTrue(is_compatible('O-', 'A+'))
        
        # AB+ is Universal Recipient
        compatible_for_ab_pos = get_compatible_donor_groups('AB+')
        self.assertEqual(len(compatible_for_ab_pos), 8)

        # O+ cannot donate to A- or O-
        self.assertFalse(is_compatible('O+', 'A-'))
        self.assertFalse(is_compatible('O+', 'O-'))

        # Distance calculation
        dist = calculate_haversine_distance(40.7128, -74.0060, 40.7180, -73.9980)
        self.assertGreater(dist, 0.0)
        self.assertLess(dist, 5.0)

        # Cooldown check
        past_date = date.today() - timedelta(days=120)
        eligible, days, _ = evaluate_donation_cooldown(past_date)
        self.assertTrue(eligible)
        self.assertEqual(days, 120)

    def test_2_auth_and_role_login(self):
        """Test authentication for different roles and credentials."""
        # 1. Login as Universal Donor Alex
        res = self.client.post('/login', data={'email': 'alex.donor@example.com', 'password': 'donor123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Alex Rivera', res.data)
        self.assertIn(b'Donor Portal', res.data)

        # 2. Logout
        res = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b'securely logged out', res.data)

        # 3. Login as Blood Bank
        res = self.client.post('/login', data={'email': 'central.bank@metroblood.org', 'password': 'bank123'}, follow_redirects=True)
        self.assertIn(b'Central Red Cross', res.data)
        self.assertIn(b'Inventory Logistics', res.data)

        # 4. Login as Admin
        self.client.get('/logout')
        res = self.client.post('/login', data={'email': 'admin@bloodcare.org', 'password': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Administrator Dashboard', res.data)
        self.client.get('/logout')

    def test_3_emergency_request_creation_and_tracking(self):
        """Test emergency request submission and automated donor matching."""
        res = self.client.post('/emergency-request', data={
            'patient_name': 'Automated Test Patient',
            'blood_group': 'O-',
            'units_needed': '2',
            'urgency': 'Critical',
            'hospital_name': 'St. Mary Memorial Hospital',
            'hospital_address': '750 Healthcare Blvd',
            'area': 'Medical District',
            'city': 'Metro City',
            'required_date': date.today().strftime('%Y-%m-%d'),
            'required_time': 'Immediate',
            'contact_phone': '+1 (555) 999-8888',
            'medical_reason': 'Automated emergency test case'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Automated Test Patient', res.data)
        self.assertIn(b'REQ-2026-', res.data)
        self.assertIn(b'Matching in Progress', res.data)

    def test_4_donor_actions(self):
        """Test donor availability toggle and match acceptance."""
        # Login as donor Priya Patel
        self.client.post('/login', data={'email': 'priya.patel@example.com', 'password': 'donor123'})
        
        # Toggle availability
        res = self.client.post('/donor/toggle-availability', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        # Fetch actual blood bank user ID from DB
        conn = get_db()
        bank_user = conn.execute("SELECT user_id FROM healthcare_organizations WHERE org_type = 'blood_bank' LIMIT 1").fetchone()
        bank_id = bank_user['user_id']
        conn.close()

        # Book appointment
        res = self.client.post('/donor/book-appointment', data={
            'blood_bank_user_id': bank_id,
            'appointment_date': (date.today() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'time_slot': '10:00 AM - 10:30 AM',
            'donor_notes': 'Test voluntary drive'
        }, follow_redirects=True)
        self.assertIn(b'booked successfully', res.data)
        self.client.get('/logout')

    def test_5_blood_bank_inventory_fifo_and_issue(self):
        """Test blood bank inventory addition, issue transaction and negative stock guard."""
        self.client.post('/login', data={'email': 'central.bank@metroblood.org', 'password': 'bank123'})
        
        # Add inventory batch
        res = self.client.post('/bloodbank/inventory/add', data={
            'blood_group': 'B-',
            'units': '10',
            'batch_number': 'TEST-BATCH-B01',
            'collection_date': date.today().strftime('%Y-%m-%d'),
            'storage_location': 'Cold Room Shelf B-1',
            'min_threshold': '5'
        }, follow_redirects=True)
        self.assertIn(b'TEST-BATCH-B01', res.data)

        # Issue units
        res = self.client.post('/bloodbank/transaction/record', data={
            'transaction_type': 'Issue',
            'blood_group': 'B-',
            'units': '3',
            'notes': 'Test issue for surgical emergency'
        }, follow_redirects=True)
        self.assertIn(b'Issue transaction of 3 unit(s)', res.data)

        # Guard: Attempt to issue excessive units (e.g. 500 units)
        res = self.client.post('/bloodbank/transaction/record', data={
            'transaction_type': 'Issue',
            'blood_group': 'B-',
            'units': '500',
            'notes': 'Illegal overdraft test'
        }, follow_redirects=True)
        self.assertIn(b'Cannot issue 500 units', res.data)
        self.client.get('/logout')

    def test_6_unauthorized_access_protection(self):
        """Test protected routes redirect unauthenticated and unauthorized roles."""
        # Unauthenticated access to donor dashboard
        res = self.client.get('/donor/dashboard', follow_redirects=True)
        self.assertIn(b'Please log in', res.data)

        # Donor trying to access Admin dashboard
        self.client.post('/login', data={'email': 'alex.donor@example.com', 'password': 'donor123'})
        res = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b'Unauthorized access', res.data)
        self.client.get('/logout')

    def test_7_multi_role_registration(self):
        """Test registration across all 5 roles: Donor, Recipient, Hospital, NGO, Blood Bank."""
        # 1. Register new Donor
        res = self.client.post('/register', data={
            'role': 'donor',
            'full_name': 'Test New Donor',
            'email': 'new.donor@example.com',
            'phone': '+1 (555) 777-1111',
            'password': 'password123',
            'city': 'Metro City',
            'area': 'Downtown',
            'blood_group': 'O+',
            'age': '28',
            'gender': 'Male',
            'consent_contact': 'on'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Test New Donor', res.data)
        self.client.get('/logout')

        # 2. Register new NGO
        res = self.client.post('/register', data={
            'role': 'ngo',
            'full_name': 'Community Care Leader',
            'email': 'community.care@ngo.org',
            'phone': '+1 (555) 777-2222',
            'password': 'password123',
            'city': 'Metro City',
            'area': 'Tech Park',
            'org_name': 'Community Care Blood NGO',
            'address': '900 Tech Blvd',
            'license_number': 'NGO-REG-9999'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Registration successful', res.data)
        self.client.get('/logout')

        # 3. Register new Hospital
        res = self.client.post('/register', data={
            'role': 'hospital',
            'full_name': 'Dr. Chief Medical',
            'email': 'city.trauma@hospital.org',
            'phone': '+1 (555) 777-3333',
            'password': 'password123',
            'city': 'Metro City',
            'area': 'Westside',
            'org_name': 'City West Trauma Center',
            'address': '550 West Ave',
            'license_number': 'HOSP-LIC-7788'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Registration successful', res.data)
        self.client.get('/logout')

    def test_8_forgot_password_flow(self):
        """Test forgot password account lookup and password reset."""
        # 1. Step 1: Lookup existing email
        res = self.client.post('/forgot-password', data={
            'email': 'sarah.jenkins@example.com'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Account verified for Sarah Jenkins', res.data)

        # 2. Step 2: Set new password
        res = self.client.post('/forgot-password', data={
            'email': 'sarah.jenkins@example.com',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Password reset successful', res.data)

        # 3. Login with the new password
        res = self.client.post('/login', data={
            'email': 'sarah.jenkins@example.com',
            'password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Sarah Jenkins', res.data)
        self.client.get('/logout')

if __name__ == '__main__':
    unittest.main()
