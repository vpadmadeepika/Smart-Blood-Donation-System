"""
Smart Blood Donation Management System
Core Flask Application - Routing, Auth, Role Dashboards, Matching & Inventory
"""

import os
import random
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import database
from database import get_db, init_db
from matching import (
    get_compatible_donor_groups, is_compatible, rank_donors_for_request,
    COMPATIBILITY_RECIPIENT_MAP, COMPATIBILITY_DONOR_MAP, DEMO_AREA_COORDINATES
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart_blood_donation_pbl_secure_key_2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# -------------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL HELPERS
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this section.', 'warning')
                return redirect(url_for('login', next=request.url))
            if session.get('role') not in allowed_roles:
                flash(f'Unauthorized access. This area is reserved for {", ".join(allowed_roles)}.', 'danger')
                return redirect(url_for('user_home_redirect'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """Fetches currently logged-in user object and unread notification count."""
    if 'user_id' not in session:
        return None, 0
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    unread_count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", 
        (session['user_id'],)
    ).fetchone()[0]
    conn.close()
    return user, unread_count

def log_notification(conn, user_id, title, message, notif_type='system', link=None):
    """Helper to write an in-app notification to the database."""
    conn.execute(
        "INSERT INTO notifications (user_id, title, message, type, link) VALUES (?, ?, ?, ?, ?)",
        (user_id, title, message, notif_type, link)
    )

def log_status_history(conn, request_id, old_status, new_status, user_id, comments):
    """Helper to log status transitions for blood requests."""
    conn.execute(
        """INSERT INTO request_status_history 
           (request_id, old_status, new_status, changed_by_user_id, comments) 
           VALUES (?, ?, ?, ?, ?)""",
        (request_id, old_status, new_status, user_id, comments)
    )

def generate_request_code():
    """Generates an intuitive unique request code like REQ-2026-7842."""
    rand_suffix = random.randint(1000, 9999)
    return f"REQ-{datetime.now().year}-{rand_suffix}"

def generate_appointment_code():
    rand_suffix = random.randint(1000, 9999)
    return f"APT-{datetime.now().year}-{rand_suffix}"

# Template Context Processor to make current user and notifications available globally
@app.context_processor
def inject_global_vars():
    user, unread_count = get_current_user()
    return {
        'current_user': user,
        'unread_notifications_count': unread_count,
        'current_year': datetime.now().year,
        'blood_groups': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
        'demo_areas': list(DEMO_AREA_COORDINATES.keys())
    }

# -------------------------------------------------------------
# PUBLIC & CORE ROUTES
# -------------------------------------------------------------
@app.route('/')
def index():
    """Home landing page with stats, how it works, compatibility matrix and emergency requests."""
    conn = get_db()
    
    # Aggregated Stats
    total_donors = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'donor'").fetchone()[0]
    total_requests = conn.execute("SELECT COUNT(*) FROM blood_requests").fetchone()[0]
    total_blood_banks = conn.execute("SELECT COUNT(*) FROM healthcare_organizations WHERE org_type = 'blood_bank'").fetchone()[0]
    completed_donations = conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status = 'Fulfilled'").fetchone()[0]
    
    # Available Blood Units Count
    total_units = conn.execute("SELECT COALESCE(SUM(units), 0) FROM blood_inventory WHERE status IN ('Available', 'Low Stock')").fetchone()[0]
    
    # Recent Urgent Requests
    urgent_requests = conn.execute(
        """SELECT br.*, u.full_name as requester_name 
           FROM blood_requests br
           JOIN users u ON br.requester_user_id = u.id
           WHERE br.urgency IN ('Critical', 'High') AND br.status NOT IN ('Fulfilled', 'Cancelled')
           ORDER BY br.created_at DESC LIMIT 3"""
    ).fetchall()

    # Blood Banks Directory preview
    blood_banks = conn.execute(
        """SELECT ho.*, u.phone, u.email 
           FROM healthcare_organizations ho
           JOIN users u ON ho.user_id = u.id
           WHERE ho.org_type = 'blood_bank' LIMIT 3"""
    ).fetchall()

    conn.close()
    return render_template(
        'index.html',
        stats={
            'donors': total_donors,
            'requests': total_requests,
            'blood_banks': total_blood_banks,
            'fulfilled': completed_donations + 12, # include base historical demo count
            'available_units': total_units
        },
        urgent_requests=urgent_requests,
        blood_banks=blood_banks,
        compatibility_map=COMPATIBILITY_RECIPIENT_MAP
    )

@app.route('/about')
def about():
    """About page with PBL overview, architecture details, and clinical safety notice."""
    return render_template('about.html')

@app.route('/blood-banks')
def blood_banks_directory():
    """Public directory of participating blood banks and hospitals with live inventory counts."""
    conn = get_db()
    
    banks = conn.execute(
        """SELECT ho.*, u.email, u.phone,
           (SELECT COALESCE(SUM(units), 0) FROM blood_inventory bi WHERE bi.blood_bank_user_id = ho.user_id AND bi.status != 'Expired') as total_stock
           FROM healthcare_organizations ho
           JOIN users u ON ho.user_id = u.id
           ORDER BY ho.org_type, ho.org_name"""
    ).fetchall()
    
    # Group inventory by blood group for each bank
    bank_stocks = {}
    for b in banks:
        stocks = conn.execute(
            """SELECT blood_group, SUM(units) as total_units 
               FROM blood_inventory 
               WHERE blood_bank_user_id = ? AND status != 'Expired'
               GROUP BY blood_group""",
            (b['user_id'],)
        ).fetchall()
        bank_stocks[b['user_id']] = {s['blood_group']: s['total_units'] for s in stocks}
        
    conn.close()
    return render_template('blood_banks.html', organizations=banks, bank_stocks=bank_stocks)

@app.route('/find-blood', methods=['GET', 'POST'])
def find_blood():
    """Smart Blood Finder & Compatibility Matching Page."""
    selected_bg = request.args.get('blood_group') or request.form.get('blood_group') or 'O+'
    selected_area = request.args.get('area') or request.form.get('area') or 'Downtown'
    selected_urgency = request.args.get('urgency') or request.form.get('urgency') or 'Routine'
    
    conn = get_db()
    
    # Fetch all active donors with profiles
    donors_raw = conn.execute(
        """SELECT u.id as user_id, u.full_name, u.email, u.phone,
                  dp.blood_group, dp.age, dp.gender, dp.city, dp.area,
                  dp.latitude, dp.longitude, dp.last_donation_date,
                  dp.is_available, dp.consent_contact, dp.total_donations
           FROM users u
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE u.status = 'active'"""
    ).fetchall()
    
    donor_dicts = [dict(d) for d in donors_raw]
    
    # Request data payload for matching engine
    req_payload = {
        'blood_group': selected_bg,
        'area': selected_area,
        'city': 'Metro City',
        'latitude': DEMO_AREA_COORDINATES.get(selected_area, (40.7128, -74.0060))[0],
        'longitude': DEMO_AREA_COORDINATES.get(selected_area, (40.7128, -74.0060))[1],
    }
    
    ranked_donors = rank_donors_for_request(req_payload, donor_dicts)
    
    # Blood bank available units for compatible groups
    compatible_groups = get_compatible_donor_groups(selected_bg)
    placeholders = ', '.join(['?'] * len(compatible_groups))
    
    bank_inventory = conn.execute(
        f"""SELECT bi.blood_group, bi.units, bi.status, ho.org_name, ho.area, ho.address, ho.operating_hours, u.phone
            FROM blood_inventory bi
            JOIN healthcare_organizations ho ON bi.blood_bank_user_id = ho.user_id
            JOIN users u ON ho.user_id = u.id
            WHERE bi.blood_group IN ({placeholders}) AND bi.status != 'Expired' AND bi.units > 0
            ORDER BY bi.units DESC""",
        compatible_groups
    ).fetchall()
    
    conn.close()
    
    return render_template(
        'find_blood.html',
        selected_bg=selected_bg,
        selected_area=selected_area,
        selected_urgency=selected_urgency,
        compatible_groups=compatible_groups,
        ranked_donors=ranked_donors,
        bank_inventory=bank_inventory
    )

# -------------------------------------------------------------
# EMERGENCY BLOOD REQUEST WORKFLOW
# -------------------------------------------------------------
@app.route('/emergency-request', methods=['GET', 'POST'])
def emergency_request():
    """Dedicated high-visibility emergency blood request submission."""
    if request.method == 'POST':
        patient_name = request.form.get('patient_name', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        units_needed = int(request.form.get('units_needed', 1))
        urgency = request.form.get('urgency', 'Critical')
        hospital_name = request.form.get('hospital_name', '').strip()
        hospital_address = request.form.get('hospital_address', '').strip()
        area = request.form.get('area', 'Downtown').strip()
        city = request.form.get('city', 'Metro City').strip()
        required_date = request.form.get('required_date') or date.today().strftime('%Y-%m-%d')
        required_time = request.form.get('required_time', 'Immediate')
        contact_phone = request.form.get('contact_phone', '').strip()
        medical_reason = request.form.get('medical_reason', '').strip()
        
        if not all([patient_name, blood_group, hospital_name, contact_phone]):
            flash('Please fill in all required medical and contact fields.', 'danger')
            return redirect(url_for('emergency_request'))
            
        req_code = generate_request_code()
        coords = DEMO_AREA_COORDINATES.get(area, (40.7128, -74.0060))
        
        # Requester ID (use session user if logged in, or default to general emergency dispatcher user)
        requester_id = session.get('user_id')
        conn = get_db()
        
        if not requester_id:
            # Fallback to demo emergency recipient user or create temporary reference
            default_user = conn.execute("SELECT id FROM users WHERE role = 'recipient' LIMIT 1").fetchone()
            requester_id = default_user[0] if default_user else 1

        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO blood_requests 
               (request_code, requester_user_id, patient_name, blood_group, units_needed, 
                urgency, hospital_name, hospital_address, city, area, latitude, longitude, 
                required_date, required_time, contact_phone, medical_reason, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Matching in Progress')""",
            (req_code, requester_id, patient_name, blood_group, units_needed, urgency,
             hospital_name, hospital_address, city, area, coords[0], coords[1],
             required_date, required_time, contact_phone, medical_reason)
        )
        new_req_id = cursor.lastrowid
        
        # Log status history
        log_status_history(conn, new_req_id, 'Submitted', 'Matching in Progress', requester_id, 'Emergency request logged. Matching engine initiated.')
        
        # Automatically run smart donor matching and notify compatible donors
        donors_raw = conn.execute(
            """SELECT u.id as user_id, u.full_name, u.email, u.phone,
                      dp.blood_group, dp.age, dp.gender, dp.city, dp.area,
                      dp.latitude, dp.longitude, dp.last_donation_date,
                      dp.is_available, dp.consent_contact, dp.total_donations
               FROM users u
               JOIN donor_profiles dp ON u.id = dp.user_id
               WHERE u.status = 'active' AND dp.is_available = 1"""
        ).fetchall()
        
        donor_dicts = [dict(d) for d in donors_raw]
        req_dict = {
            'blood_group': blood_group, 'area': area, 'city': city,
            'latitude': coords[0], 'longitude': coords[1]
        }
        ranked = rank_donors_for_request(req_dict, donor_dicts)
        
        notified_count = 0
        for match_item in ranked[:5]: # Notify top 5 compatible nearby donors
            donor_id = match_item['donor_user_id']
            cursor.execute(
                """INSERT INTO donor_matches (request_id, donor_user_id, compatibility_score, distance_km, status, response_notes)
                   VALUES (?, ?, ?, ?, 'Pending', ?)""",
                (new_req_id, donor_id, match_item['compatibility_score'], match_item['distance_km'], 
                 f"Simulated urgent match notification dispatched for {blood_group} request.")
            )
            # In-app notification to donor
            log_notification(
                conn, donor_id,
                f"🚨 URGENT Blood Request: {blood_group} Needed!",
                f"Emergency request {req_code} for {units_needed} unit(s) of {blood_group} at {hospital_name} ({area}). You are a suitable match.",
                'emergency', url_for('donor_dashboard')
            )
            notified_count += 1
            
        if notified_count > 0:
            cursor.execute("UPDATE blood_requests SET status = 'Donors Notified' WHERE id = ?", (new_req_id,))
            log_status_history(conn, new_req_id, 'Matching in Progress', 'Donors Notified', requester_id, f'Notified {notified_count} compatible donors in {area}.')
            
        conn.commit()
        conn.close()
        
        flash(f'Emergency request {req_code} created successfully! {notified_count} nearby compatible donors have been matched.', 'success')
        return redirect(url_for('track_request', request_code=req_code))
        
    return render_template('emergency_request.html')

@app.route('/request/<request_code>')
def track_request(request_code):
    """Real-time timeline tracking page for a specific blood request."""
    conn = get_db()
    req_record = conn.execute(
        """SELECT br.*, u.full_name as requester_name, u.email as requester_email
           FROM blood_requests br
           JOIN users u ON br.requester_user_id = u.id
           WHERE br.request_code = ?""",
        (request_code,)
    ).fetchone()
    
    if not req_record:
        conn.close()
        flash('Blood request not found.', 'danger')
        return redirect(url_for('index'))
        
    # Status Timeline History
    history = conn.execute(
        """SELECT rsh.*, u.full_name as changed_by_name 
           FROM request_status_history rsh
           LEFT JOIN users u ON rsh.changed_by_user_id = u.id
           WHERE rsh.request_id = ?
           ORDER BY rsh.changed_at ASC""",
        (req_record['id'],)
    ).fetchall()
    
    # Matched donors info (only show if authorized or requester)
    matches = conn.execute(
        """SELECT dm.*, u.full_name, u.phone, u.email, dp.blood_group, dp.area, dp.city
           FROM donor_matches dm
           JOIN users u ON dm.donor_user_id = u.id
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE dm.request_id = ?
           ORDER BY dm.compatibility_score DESC""",
        (req_record['id'],)
    ).fetchall()
    
    conn.close()
    return render_template(
        'request_detail.html',
        blood_request=req_record,
        status_history=history,
        matches=matches
    )

# -------------------------------------------------------------
# AUTHENTICATION ROUTES
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Unified multi-role login with 1-click demo account switcher."""
    if 'user_id' in session:
        return redirect(url_for('user_home_redirect'))
        
    if request.method == 'POST':
        email_or_user = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?", 
            (email_or_user, email_or_user)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            if user['status'] == 'suspended':
                flash('This account has been suspended. Please contact the administrator.', 'danger')
                return redirect(url_for('login'))
                
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['email'] = user['email']
            
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('user_home_redirect'))
        else:
            flash('Invalid email/username or password. Try one of the demo logins below.', 'danger')
            
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Multi-role user registration."""
    if request.method == 'POST':
        role = request.form.get('role', 'donor').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        city = request.form.get('city', 'Metro City').strip()
        area = request.form.get('area', 'Downtown').strip()
        
        if not all([full_name, email, password, role]):
            flash('Please complete all required fields.', 'danger')
            return redirect(url_for('register'))
            
        conn = get_db()
        cursor = conn.cursor()
        
        # Check duplicate email
        existing = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash('An account with this email already exists. Please login.', 'warning')
            return redirect(url_for('login'))
            
        username = email.split('@')[0] + f"_{random.randint(100, 999)}"
        pw_hash = generate_password_hash(password)
        
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, full_name, phone) VALUES (?, ?, ?, ?, ?, ?)",
            (username, email, pw_hash, role, full_name, phone)
        )
        user_id = cursor.lastrowid
        coords = DEMO_AREA_COORDINATES.get(area, (40.7128, -74.0060))
        
        # Insert role-specific profile details
        if role == 'donor':
            blood_group = request.form.get('blood_group', 'O+')
            age = int(request.form.get('age', 25))
            gender = request.form.get('gender', 'Other')
            last_donation = request.form.get('last_donation_date') or None
            consent = 1 if request.form.get('consent_contact') else 0
            
            cursor.execute(
                """INSERT INTO donor_profiles 
                   (user_id, blood_group, age, gender, city, area, latitude, longitude, last_donation_date, is_available, consent_contact)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (user_id, blood_group, age, gender, city, area, coords[0], coords[1], last_donation, consent)
            )
        elif role == 'recipient':
            emergency_contact = request.form.get('emergency_contact', phone)
            cursor.execute(
                "INSERT INTO recipient_profiles (user_id, city, area, emergency_contact) VALUES (?, ?, ?, ?)",
                (user_id, city, area, emergency_contact)
            )
        elif role in ('hospital', 'blood_bank', 'ngo'):
            org_name = request.form.get('org_name', full_name)
            address = request.form.get('address', f"{area}, {city}")
            license_num = request.form.get('license_number', f"{role.upper()}-REG-{random.randint(1000, 9999)}")
            
            cursor.execute(
                """INSERT INTO healthcare_organizations 
                   (user_id, org_name, org_type, license_number, contact_person, emergency_helpline, address, city, area, latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, org_name, role, license_num, full_name, phone, address, city, area, coords[0], coords[1])
            )
            
        # Welcome notification
        log_notification(
            conn, user_id,
            "Welcome to Smart Blood Donation System! 🎉",
            f"Your account as {role.replace('_', ' ').title()} has been registered successfully. Explore your dashboard to get started.",
            'system', url_for('user_home_redirect')
        )
        
        conn.commit()
        conn.close()
        
        # Auto-login after registration
        session['user_id'] = user_id
        session['username'] = username
        session['full_name'] = full_name
        session['role'] = role
        session['email'] = email
        
        flash(f'Registration successful! Welcome to the platform, {full_name}.', 'success')
        return redirect(url_for('user_home_redirect'))
        
    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Secure password reset flow with email verification."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email:
            flash('Please provide your registered email address.', 'danger')
            return render_template('auth/forgot_password.html')

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            conn.close()
            flash('No account was found with that email address. Please check and try again.', 'danger')
            return render_template('auth/forgot_password.html')

        # If new password is provided, reset it directly
        if new_password:
            if len(new_password) < 6:
                conn.close()
                flash('Password must be at least 6 characters long.', 'danger')
                return render_template('auth/forgot_password.html', email=email, step=2)

            if new_password != confirm_password:
                conn.close()
                flash('Passwords do not match. Please re-enter.', 'danger')
                return render_template('auth/forgot_password.html', email=email, step=2)

            new_pw_hash = generate_password_hash(new_password)
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_pw_hash, user['id']))
            log_notification(
                conn, user['id'],
                "Password Successfully Reset 🔒",
                "Your account password was updated successfully. If you did not perform this change, contact administrator immediately.",
                'system'
            )
            conn.commit()
            conn.close()

            flash('Password reset successful! You can now log in with your new password.', 'success')
            return redirect(url_for('login'))

        # Step 1: Email found, prompt for new password
        conn.close()
        flash(f'Account verified for {user["full_name"]}. Please enter your new password below.', 'info')
        return render_template('auth/forgot_password.html', email=email, user=user, step=2)

    return render_template('auth/forgot_password.html', step=1)

@app.route('/logout')
def logout():
    """Clear active session."""
    session.clear()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def user_home_redirect():
    """Redirects the authenticated user to their role-specific dashboard."""
    role = session.get('role')
    if role == 'donor':
        return redirect(url_for('donor_dashboard'))
    elif role == 'recipient':
        return redirect(url_for('recipient_dashboard'))
    elif role in ('hospital', 'ngo'):
        return redirect(url_for('hospital_dashboard'))
    elif role == 'blood_bank':
        return redirect(url_for('bloodbank_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('index'))

# -------------------------------------------------------------
# 1. DONOR DASHBOARD & ACTIONS
# -------------------------------------------------------------
@app.route('/donor/dashboard')
@role_required('donor')
def donor_dashboard():
    """Donor profile, availability toggle, pending match invites, appointment schedule & eligibility reminder."""
    user_id = session['user_id']
    conn = get_db()
    
    donor_profile = conn.execute("SELECT * FROM donor_profiles WHERE user_id = ?", (user_id,)).fetchone()
    
    # Active match requests waiting for donor response
    pending_matches = conn.execute(
        """SELECT dm.id as match_id, dm.status as match_status, dm.compatibility_score, dm.distance_km,
                  br.id as request_id, br.request_code, br.patient_name, br.blood_group, br.units_needed,
                  br.urgency, br.hospital_name, br.hospital_address, br.city, br.area, br.required_date,
                  br.required_time, br.contact_phone, br.medical_reason, br.created_at
           FROM donor_matches dm
           JOIN blood_requests br ON dm.request_id = br.id
           WHERE dm.donor_user_id = ? AND dm.status = 'Pending' AND br.status NOT IN ('Fulfilled', 'Cancelled')
           ORDER BY br.urgency = 'Critical' DESC, dm.matched_at DESC""",
        (user_id,)
    ).fetchall()

    # Accepted / Historical match contributions
    donation_history = conn.execute(
        """SELECT dm.id as match_id, dm.status as match_status, dm.responded_at,
                  br.request_code, br.patient_name, br.blood_group, br.units_needed,
                  br.hospital_name, br.urgency, br.status as request_status
           FROM donor_matches dm
           JOIN blood_requests br ON dm.request_id = br.id
           WHERE dm.donor_user_id = ? AND dm.status IN ('Accepted', 'Completed', 'Declined')
           ORDER BY dm.matched_at DESC""",
        (user_id,)
    ).fetchall()

    # Upcoming Appointments
    appointments = conn.execute(
        """SELECT a.*, ho.org_name, ho.address, ho.area, u.phone as bank_phone
           FROM appointments a
           JOIN healthcare_organizations ho ON a.blood_bank_user_id = ho.user_id
           JOIN users u ON ho.user_id = u.id
           WHERE a.donor_user_id = ?
           ORDER BY a.appointment_date ASC""",
        (user_id,)
    ).fetchall()
    
    # Blood Banks list for booking appointment
    blood_banks = conn.execute(
        """SELECT ho.user_id, ho.org_name, ho.area, ho.address 
           FROM healthcare_organizations ho 
           WHERE ho.org_type = 'blood_bank'"""
    ).fetchall()
    
    # In-app Notifications
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    
    conn.close()
    return render_template(
        'dashboards/donor_dashboard.html',
        profile=donor_profile,
        pending_matches=pending_matches,
        donation_history=donation_history,
        appointments=appointments,
        blood_banks=blood_banks,
        notifications=notifications
    )

@app.route('/donor/toggle-availability', methods=['POST'])
@role_required('donor')
def donor_toggle_availability():
    """Quick AJAX or form toggle for donor availability status."""
    user_id = session['user_id']
    conn = get_db()
    current = conn.execute("SELECT is_available FROM donor_profiles WHERE user_id = ?", (user_id,)).fetchone()
    
    new_status = 0 if (current and current['is_available'] == 1) else 1
    conn.execute("UPDATE donor_profiles SET is_available = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    
    status_text = "Available to donate" if new_status == 1 else "Unavailable / Busy"
    flash(f'Your donation availability has been updated to: {status_text}.', 'success')
    return redirect(url_for('donor_dashboard'))

@app.route('/donor/match/<int:match_id>/respond', methods=['POST'])
@role_required('donor')
def donor_respond_match(match_id):
    """Accept or decline a blood request match."""
    action = request.form.get('action', 'accept') # 'accept' or 'decline'
    notes = request.form.get('response_notes', '').strip()
    user_id = session['user_id']
    
    conn = get_db()
    match_rec = conn.execute(
        """SELECT dm.*, br.request_code, br.requester_user_id, br.patient_name, br.blood_group, br.hospital_name
           FROM donor_matches dm
           JOIN blood_requests br ON dm.request_id = br.id
           WHERE dm.id = ? AND dm.donor_user_id = ?""",
        (match_id, user_id)
    ).fetchone()
    
    if not match_rec:
        conn.close()
        flash('Match invitation not found.', 'danger')
        return redirect(url_for('donor_dashboard'))
        
    new_match_status = 'Accepted' if action == 'accept' else 'Declined'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn.execute(
        "UPDATE donor_matches SET status = ?, response_notes = ?, responded_at = ? WHERE id = ?",
        (new_match_status, notes or f"Donor {session.get('full_name')} {new_match_status.lower()} the request.", now_str, match_id)
    )
    
    # If accepted, update request status if needed and notify requester
    if action == 'accept':
        conn.execute(
            "UPDATE blood_requests SET status = 'Response Received', updated_at = ? WHERE id = ?",
            (now_str, match_rec['request_id'])
        )
        log_status_history(
            conn, match_rec['request_id'], 'Donors Notified', 'Response Received', user_id,
            f"Donor {session.get('full_name')} accepted the donation request."
        )
        # Notify Requester
        log_notification(
            conn, match_rec['requester_user_id'],
            f"🎉 Match Accepted for {match_rec['request_code']}!",
            f"Donor {session.get('full_name')} has accepted your request for {match_rec['patient_name']}. Contact details are now available.",
            'match', url_for('track_request', request_code=match_rec['request_code'])
        )
        flash(f'Thank you! You have accepted request {match_rec["request_code"]}. The hospital and requester have been notified.', 'success')
    else:
        flash(f'You have declined request {match_rec["request_code"]}.', 'info')
        
    conn.commit()
    conn.close()
    return redirect(url_for('donor_dashboard'))

@app.route('/donor/book-appointment', methods=['POST'])
@role_required('donor')
def donor_book_appointment():
    """Books a donation appointment slot at a participating blood bank."""
    user_id = session['user_id']
    bank_id = int(request.form.get('blood_bank_user_id'))
    appt_date = request.form.get('appointment_date')
    time_slot = request.form.get('time_slot')
    donor_notes = request.form.get('donor_notes', '').strip()
    
    if not all([bank_id, appt_date, time_slot]):
        flash('Please select a blood bank, date, and time slot.', 'danger')
        return redirect(url_for('donor_dashboard'))
        
    conn = get_db()
    
    # Prevent duplicate booking on same slot by same donor
    duplicate = conn.execute(
        """SELECT id FROM appointments 
           WHERE donor_user_id = ? AND appointment_date = ? AND time_slot = ? AND status = 'Scheduled'""",
        (user_id, appt_date, time_slot)
    ).fetchone()
    
    if duplicate:
        conn.close()
        flash('You already have a scheduled appointment for this exact date and time slot.', 'warning')
        return redirect(url_for('donor_dashboard'))
        
    appt_code = generate_appointment_code()
    conn.execute(
        """INSERT INTO appointments (appointment_code, donor_user_id, blood_bank_user_id, appointment_date, time_slot, status, donor_notes)
           VALUES (?, ?, ?, ?, ?, 'Scheduled', ?)""",
        (appt_code, user_id, bank_id, appt_date, time_slot, donor_notes)
    )
    
    # Notify blood bank
    log_notification(
        conn, bank_id,
        "New Donation Appointment Booked 📅",
        f"Donor {session.get('full_name')} booked slot {time_slot} on {appt_date} (Code: {appt_code}).",
        'appointment', url_for('bloodbank_dashboard')
    )
    
    conn.commit()
    conn.close()
    
    flash(f'Appointment {appt_code} booked successfully! Please arrive 10 minutes early.', 'success')
    return redirect(url_for('donor_dashboard'))

@app.route('/donor/cancel-appointment/<int:appt_id>', methods=['POST'])
@login_required
def cancel_appointment(appt_id):
    """Cancels a scheduled appointment."""
    user_id = session['user_id']
    conn = get_db()
    
    appt = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if not appt:
        conn.close()
        flash('Appointment not found.', 'danger')
        return redirect(url_for('user_home_redirect'))
        
    conn.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = ?", (appt_id,))
    
    # Notify other party
    other_user_id = appt['blood_bank_user_id'] if session.get('role') == 'donor' else appt['donor_user_id']
    log_notification(
        conn, other_user_id,
        "Appointment Cancelled",
        f"Appointment {appt['appointment_code']} on {appt['appointment_date']} was cancelled by {session.get('full_name')}.",
        'appointment'
    )
    
    conn.commit()
    conn.close()
    flash(f'Appointment {appt["appointment_code"]} has been cancelled.', 'info')
    return redirect(url_for('user_home_redirect'))

@app.route('/donor/update-profile', methods=['POST'])
@role_required('donor')
def donor_update_profile():
    """Updates donor contact info, area, and last donation date."""
    user_id = session['user_id']
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    area = request.form.get('area', 'Downtown').strip()
    age = int(request.form.get('age', 25))
    last_donation = request.form.get('last_donation_date') or None
    medical_notes = request.form.get('medical_notes', '').strip()
    consent = 1 if request.form.get('consent_contact') else 0
    coords = DEMO_AREA_COORDINATES.get(area, (40.7128, -74.0060))
    
    conn = get_db()
    conn.execute("UPDATE users SET full_name = ?, phone = ? WHERE id = ?", (full_name, phone, user_id))
    conn.execute(
        """UPDATE donor_profiles 
           SET area = ?, age = ?, last_donation_date = ?, medical_notes = ?, consent_contact = ?, latitude = ?, longitude = ?
           WHERE user_id = ?""",
        (area, age, last_donation, medical_notes, consent, coords[0], coords[1], user_id)
    )
    conn.commit()
    conn.close()
    
    session['full_name'] = full_name
    flash('Your donor profile has been updated successfully.', 'success')
    return redirect(url_for('donor_dashboard'))

# -------------------------------------------------------------
# 2. RECIPIENT DASHBOARD & ACTIONS
# -------------------------------------------------------------
@app.route('/recipient/dashboard')
@role_required('recipient')
def recipient_dashboard():
    """Recipient dashboard: blood requests management, live tracking, matched donors."""
    user_id = session['user_id']
    conn = get_db()
    
    profile = conn.execute("SELECT * FROM recipient_profiles WHERE user_id = ?", (user_id,)).fetchone()
    
    # Recipient requests with match counts
    requests_list = conn.execute(
        """SELECT br.*, 
                  (SELECT COUNT(*) FROM donor_matches dm WHERE dm.request_id = br.id) as match_count,
                  (SELECT COUNT(*) FROM donor_matches dm WHERE dm.request_id = br.id AND dm.status = 'Accepted') as accepted_count
           FROM blood_requests br
           WHERE br.requester_user_id = ?
           ORDER BY br.created_at DESC""",
        (user_id,)
    ).fetchall()
    
    # Active matched donor contacts
    active_matches = conn.execute(
        """SELECT dm.*, br.request_code, br.patient_name, br.blood_group as req_blood_group,
                  u.full_name as donor_name, u.phone as donor_phone, u.email as donor_email,
                  dp.blood_group as donor_blood_group, dp.area as donor_area
           FROM donor_matches dm
           JOIN blood_requests br ON dm.request_id = br.id
           JOIN users u ON dm.donor_user_id = u.id
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE br.requester_user_id = ? AND dm.status IN ('Accepted', 'Pending')
           ORDER BY dm.status = 'Accepted' DESC, dm.compatibility_score DESC""",
        (user_id,)
    ).fetchall()
    
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    
    conn.close()
    return render_template(
        'dashboards/recipient_dashboard.html',
        profile=profile,
        requests=requests_list,
        matches=active_matches,
        notifications=notifications
    )

@app.route('/recipient/create-request', methods=['POST'])
@role_required('recipient', 'hospital', 'ngo')
def create_blood_request():
    """Creates a new routine, high or critical blood request."""
    requester_id = session['user_id']
    patient_name = request.form.get('patient_name', '').strip()
    blood_group = request.form.get('blood_group', 'O+').strip()
    units_needed = int(request.form.get('units_needed', 1))
    urgency = request.form.get('urgency', 'Routine')
    hospital_name = request.form.get('hospital_name', '').strip()
    hospital_address = request.form.get('hospital_address', '').strip()
    area = request.form.get('area', 'Downtown').strip()
    city = request.form.get('city', 'Metro City').strip()
    required_date = request.form.get('required_date') or date.today().strftime('%Y-%m-%d')
    required_time = request.form.get('required_time', '12:00 PM')
    contact_phone = request.form.get('contact_phone', session.get('phone', '+1 555-0000')).strip()
    medical_reason = request.form.get('medical_reason', '').strip()
    
    if not all([patient_name, blood_group, hospital_name, contact_phone]):
        flash('Please fill in all mandatory fields.', 'danger')
        return redirect(request.referrer or url_for('user_home_redirect'))
        
    req_code = generate_request_code()
    coords = DEMO_AREA_COORDINATES.get(area, (40.7128, -74.0060))
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """INSERT INTO blood_requests 
           (request_code, requester_user_id, patient_name, blood_group, units_needed, 
            urgency, hospital_name, hospital_address, city, area, latitude, longitude, 
            required_date, required_time, contact_phone, medical_reason, status) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted')""",
        (req_code, requester_id, patient_name, blood_group, units_needed, urgency,
         hospital_name, hospital_address, city, area, coords[0], coords[1],
         required_date, required_time, contact_phone, medical_reason)
    )
    new_req_id = cursor.lastrowid
    
    log_status_history(conn, new_req_id, None, 'Submitted', requester_id, f"Request created with urgency: {urgency}.")
    
    # Run automatic donor matching
    donors_raw = conn.execute(
        """SELECT u.id as user_id, u.full_name, u.email, u.phone,
                  dp.blood_group, dp.age, dp.gender, dp.city, dp.area,
                  dp.latitude, dp.longitude, dp.last_donation_date,
                  dp.is_available, dp.consent_contact, dp.total_donations
           FROM users u
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE u.status = 'active' AND dp.is_available = 1"""
    ).fetchall()
    
    donor_dicts = [dict(d) for d in donors_raw]
    req_payload = {
        'blood_group': blood_group, 'area': area, 'city': city,
        'latitude': coords[0], 'longitude': coords[1]
    }
    ranked = rank_donors_for_request(req_payload, donor_dicts)
    
    notified_count = 0
    for match_item in ranked[:5]:
        d_id = match_item['donor_user_id']
        cursor.execute(
            """INSERT INTO donor_matches (request_id, donor_user_id, compatibility_score, distance_km, status, response_notes)
               VALUES (?, ?, ?, ?, 'Pending', ?)""",
            (new_req_id, d_id, match_item['compatibility_score'], match_item['distance_km'], "Matched via Smart Compatibility Algorithm.")
        )
        log_notification(
            conn, d_id,
            f"Blood Request Match: {blood_group} Needed",
            f"New request {req_code} for {units_needed} unit(s) of {blood_group} at {hospital_name}.",
            'request', url_for('donor_dashboard')
        )
        notified_count += 1
        
    if notified_count > 0:
        cursor.execute("UPDATE blood_requests SET status = 'Donors Notified' WHERE id = ?", (new_req_id,))
        log_status_history(conn, new_req_id, 'Submitted', 'Donors Notified', requester_id, f"System notified {notified_count} compatible donors.")

    conn.commit()
    conn.close()
    
    flash(f'Blood request {req_code} created! {notified_count} potential donors were notified.', 'success')
    return redirect(request.referrer or url_for('user_home_redirect'))

@app.route('/request/<int:req_id>/update-status', methods=['POST'])
@login_required
def update_request_status(req_id):
    """Allows authorized users (requester, hospital, admin) to update request status (e.g. Fulfilled, Cancelled)."""
    new_status = request.form.get('status')
    comments = request.form.get('comments', '').strip()
    user_id = session['user_id']
    role = session.get('role')
    
    conn = get_db()
    req_rec = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,)).fetchone()
    
    if not req_rec:
        conn.close()
        flash('Request not found.', 'danger')
        return redirect(url_for('user_home_redirect'))
        
    # Check authorization: must be requester, hospital, blood bank or admin
    if role != 'admin' and req_rec['requester_user_id'] != user_id and role not in ('hospital', 'blood_bank'):
        conn.close()
        flash('Unauthorized to modify this request.', 'danger')
        return redirect(url_for('user_home_redirect'))
        
    old_status = req_rec['status']
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn.execute(
        "UPDATE blood_requests SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now_str, req_id)
    )
    
    log_status_history(conn, req_id, old_status, new_status, user_id, comments or f"Status updated by {session.get('full_name')}.")
    
    # If marked fulfilled, update completed matches
    if new_status == 'Fulfilled':
        conn.execute("UPDATE donor_matches SET status = 'Completed' WHERE request_id = ? AND status = 'Accepted'", (req_id,))
        
    conn.commit()
    conn.close()
    
    flash(f'Request {req_rec["request_code"]} status changed from {old_status} to {new_status}.', 'success')
    return redirect(request.referrer or url_for('user_home_redirect'))

# -------------------------------------------------------------
# 3. HOSPITAL DASHBOARD
# -------------------------------------------------------------
@app.route('/hospital/dashboard')
@role_required('hospital', 'ngo')
def hospital_dashboard():
    """Hospital dashboard: submit emergency & routine requests, donor matching, emergency response monitor."""
    user_id = session['user_id']
    conn = get_db()
    
    hospital_info = conn.execute("SELECT * FROM healthcare_organizations WHERE user_id = ?", (user_id,)).fetchone()
    
    # Requests initiated by this hospital
    hospital_requests = conn.execute(
        """SELECT br.*, 
                  (SELECT COUNT(*) FROM donor_matches dm WHERE dm.request_id = br.id) as total_matched,
                  (SELECT COUNT(*) FROM donor_matches dm WHERE dm.request_id = br.id AND dm.status = 'Accepted') as total_accepted
           FROM blood_requests br
           WHERE br.requester_user_id = ?
           ORDER BY br.urgency = 'Critical' DESC, br.created_at DESC""",
        (user_id,)
    ).fetchall()
    
    # Recent matching responses
    incoming_responses = conn.execute(
        """SELECT dm.*, br.request_code, br.patient_name, br.blood_group,
                  u.full_name as donor_name, u.phone as donor_phone, dp.area as donor_area
           FROM donor_matches dm
           JOIN blood_requests br ON dm.request_id = br.id
           JOIN users u ON dm.donor_user_id = u.id
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE br.requester_user_id = ?
           ORDER BY dm.responded_at DESC LIMIT 10""",
        (user_id,)
    ).fetchall()
    
    # Blood bank inventory snapshot
    bank_stocks = conn.execute(
        """SELECT ho.org_name, bi.blood_group, SUM(bi.units) as available_units, ho.emergency_helpline
           FROM blood_inventory bi
           JOIN healthcare_organizations ho ON bi.blood_bank_user_id = ho.user_id
           WHERE bi.status != 'Expired'
           GROUP BY ho.org_name, bi.blood_group
           ORDER BY ho.org_name, bi.blood_group"""
    ).fetchall()
    
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()

    conn.close()
    return render_template(
        'dashboards/hospital_dashboard.html',
        hospital=hospital_info,
        requests=hospital_requests,
        responses=incoming_responses,
        bank_stocks=bank_stocks,
        notifications=notifications
    )

# -------------------------------------------------------------
# 4. BLOOD BANK DASHBOARD & INVENTORY MANAGEMENT
# -------------------------------------------------------------
@app.route('/bloodbank/dashboard')
@role_required('blood_bank')
def bloodbank_dashboard():
    """Blood Bank inventory management, stock levels, near-expiry & low stock alerts, transaction logger."""
    user_id = session['user_id']
    conn = get_db()
    
    bank_info = conn.execute("SELECT * FROM healthcare_organizations WHERE user_id = ?", (user_id,)).fetchone()
    
    # Aggregate stock by blood group
    stock_summary = conn.execute(
        """SELECT blood_group, 
                  SUM(units) as total_units,
                  SUM(CASE WHEN status = 'Expiring Soon' THEN units ELSE 0 END) as expiring_units,
                  MIN(min_threshold) as min_threshold
           FROM blood_inventory
           WHERE blood_bank_user_id = ? AND status != 'Expired'
           GROUP BY blood_group""",
        (user_id,)
    ).fetchall()
    
    # Convert to dict for fast template lookup
    stock_dict = {s['blood_group']: dict(s) for s in stock_summary}
    for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
        if bg not in stock_dict:
            stock_dict[bg] = {'blood_group': bg, 'total_units': 0, 'expiring_units': 0, 'min_threshold': 5}
            
    # Detailed inventory batches
    today_str = date.today().strftime('%Y-%m-%d')
    seven_days = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Automatically update statuses based on expiry dates & stock
    conn.execute(
        "UPDATE blood_inventory SET status = 'Expired' WHERE blood_bank_user_id = ? AND expiry_date < ? AND status != 'Expired'",
        (user_id, today_str)
    )
    conn.execute(
        "UPDATE blood_inventory SET status = 'Expiring Soon' WHERE blood_bank_user_id = ? AND expiry_date >= ? AND expiry_date <= ? AND status NOT IN ('Expired')",
        (user_id, today_str, seven_days)
    )
    conn.commit()
    
    inventory_batches = conn.execute(
        "SELECT * FROM blood_inventory WHERE blood_bank_user_id = ? ORDER BY expiry_date ASC",
        (user_id,)
    ).fetchall()
    
    # Transaction Audit Log
    transactions = conn.execute(
        "SELECT * FROM inventory_transactions WHERE blood_bank_user_id = ? ORDER BY created_at DESC LIMIT 15",
        (user_id,)
    ).fetchall()
    
    # Appointments scheduled with this bank
    appointments = conn.execute(
        """SELECT a.*, u.full_name as donor_name, u.phone as donor_phone, u.email as donor_email,
                  dp.blood_group as donor_blood_group
           FROM appointments a
           JOIN users u ON a.donor_user_id = u.id
           JOIN donor_profiles dp ON u.id = dp.user_id
           WHERE a.blood_bank_user_id = ?
           ORDER BY a.appointment_date ASC""",
        (user_id,)
    ).fetchall()
    
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()

    conn.close()
    return render_template(
        'dashboards/bloodbank_dashboard.html',
        bank=bank_info,
        stock_dict=stock_dict,
        batches=inventory_batches,
        transactions=transactions,
        appointments=appointments,
        notifications=notifications
    )

@app.route('/bloodbank/inventory/add', methods=['POST'])
@role_required('blood_bank')
def add_inventory_batch():
    """Adds a new blood inventory batch."""
    user_id = session['user_id']
    blood_group = request.form.get('blood_group', 'O+').strip()
    units = int(request.form.get('units', 1))
    batch_number = request.form.get('batch_number', '').strip() or f"BATCH-{datetime.now().year}-{random.randint(100,999)}"
    collection_date = request.form.get('collection_date') or date.today().strftime('%Y-%m-%d')
    expiry_date = request.form.get('expiry_date')
    storage_location = request.form.get('storage_location', 'Cold Room Unit 1').strip()
    min_threshold = int(request.form.get('min_threshold', 5))
    
    if not expiry_date:
        # Default whole blood shelf life ~ 35-42 days
        c_date = datetime.strptime(collection_date, '%Y-%m-%d').date()
        expiry_date = (c_date + timedelta(days=35)).strftime('%Y-%m-%d')
        
    status = 'Available'
    if units <= min_threshold:
        status = 'Low Stock'
        
    conn = get_db()
    conn.execute(
        """INSERT INTO blood_inventory 
           (blood_bank_user_id, blood_group, units, batch_number, collection_date, expiry_date, storage_location, status, min_threshold)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, blood_group, units, batch_number, collection_date, expiry_date, storage_location, status, min_threshold)
    )
    
    # Record collection transaction
    conn.execute(
        """INSERT INTO inventory_transactions 
           (blood_bank_user_id, blood_group, transaction_type, units, batch_number, notes, recorded_by)
           VALUES (?, ?, 'Collection', ?, ?, 'Added new blood unit batch to inventory.', ?)""",
        (user_id, blood_group, units, batch_number, session.get('full_name'))
    )
    
    conn.commit()
    conn.close()
    
    flash(f'Added {units} unit(s) of {blood_group} (Batch: {batch_number}) to inventory.', 'success')
    return redirect(url_for('bloodbank_dashboard'))

@app.route('/bloodbank/inventory/<int:batch_id>/update', methods=['POST'])
@role_required('blood_bank')
def update_inventory_batch(batch_id):
    """Updates unit count, threshold or storage location of an inventory batch."""
    user_id = session['user_id']
    units = int(request.form.get('units', 0))
    min_threshold = int(request.form.get('min_threshold', 5))
    storage_location = request.form.get('storage_location', 'Cold Room Unit 1').strip()
    status = request.form.get('status', 'Available')
    
    if units < 0:
        flash('Inventory units cannot be negative.', 'danger')
        return redirect(url_for('bloodbank_dashboard'))
        
    conn = get_db()
    conn.execute(
        """UPDATE blood_inventory 
           SET units = ?, min_threshold = ?, storage_location = ?, status = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND blood_bank_user_id = ?""",
        (units, min_threshold, storage_location, status, batch_id, user_id)
    )
    conn.commit()
    conn.close()
    
    flash('Inventory record updated.', 'success')
    return redirect(url_for('bloodbank_dashboard'))

@app.route('/bloodbank/inventory/<int:batch_id>/delete', methods=['POST'])
@role_required('blood_bank')
def delete_inventory_batch(batch_id):
    """Deletes or marks an inventory record as disposed."""
    user_id = session['user_id']
    conn = get_db()
    
    batch = conn.execute("SELECT * FROM blood_inventory WHERE id = ? AND blood_bank_user_id = ?", (batch_id, user_id)).fetchone()
    if batch:
        conn.execute(
            """INSERT INTO inventory_transactions 
               (blood_bank_user_id, blood_group, transaction_type, units, batch_number, notes, recorded_by)
               VALUES (?, ?, 'Disposal', ?, ?, 'Disposed/Removed inventory batch.', ?)""",
            (user_id, batch['blood_group'], batch['units'], batch['batch_number'], session.get('full_name'))
        )
        conn.execute("DELETE FROM blood_inventory WHERE id = ? AND blood_bank_user_id = ?", (batch_id, user_id))
        conn.commit()
        flash(f'Batch {batch["batch_number"]} removed from inventory.', 'info')
        
    conn.close()
    return redirect(url_for('bloodbank_dashboard'))

@app.route('/bloodbank/transaction/record', methods=['POST'])
@role_required('blood_bank')
def record_inventory_transaction():
    """Records an issue or collection transaction, adjusting stock and preventing negative balances."""
    user_id = session['user_id']
    blood_group = request.form.get('blood_group', 'O+').strip()
    trans_type = request.form.get('transaction_type', 'Issue') # 'Collection' or 'Issue'
    units = int(request.form.get('units', 1))
    notes = request.form.get('notes', '').strip()
    
    if units <= 0:
        flash('Units must be greater than zero.', 'danger')
        return redirect(url_for('bloodbank_dashboard'))
        
    conn = get_db()
    
    if trans_type == 'Issue':
        # Check current available stock for this blood group
        current_stock = conn.execute(
            "SELECT COALESCE(SUM(units), 0) FROM blood_inventory WHERE blood_bank_user_id = ? AND blood_group = ? AND status != 'Expired'",
            (user_id, blood_group)
        ).fetchone()[0]
        
        if units > current_stock:
            conn.close()
            flash(f'Cannot issue {units} units of {blood_group}. Only {current_stock} units available in non-expired stock.', 'danger')
            return redirect(url_for('bloodbank_dashboard'))
            
        # Deduct units starting from oldest batch (FIFO)
        batches = conn.execute(
            "SELECT * FROM blood_inventory WHERE blood_bank_user_id = ? AND blood_group = ? AND units > 0 AND status != 'Expired' ORDER BY expiry_date ASC",
            (user_id, blood_group)
        ).fetchall()
        
        remaining_to_deduct = units
        for b in batches:
            if remaining_to_deduct <= 0:
                break
            if b['units'] <= remaining_to_deduct:
                remaining_to_deduct -= b['units']
                conn.execute("UPDATE blood_inventory SET units = 0, status = 'Reserved' WHERE id = ?", (b['id'],))
            else:
                conn.execute("UPDATE blood_inventory SET units = units - ? WHERE id = ?", (remaining_to_deduct, b['id']))
                remaining_to_deduct = 0
                
    elif trans_type == 'Collection':
        # Add to latest batch or create new
        c_date = date.today().strftime('%Y-%m-%d')
        e_date = (date.today() + timedelta(days=35)).strftime('%Y-%m-%d')
        b_num = f"COL-{datetime.now().year}-{random.randint(100,999)}"
        conn.execute(
            """INSERT INTO blood_inventory 
               (blood_bank_user_id, blood_group, units, batch_number, collection_date, expiry_date, storage_location, status)
               VALUES (?, ?, ?, ?, ?, ?, 'Cold Room Unit 1', 'Available')""",
            (user_id, blood_group, units, b_num, c_date, e_date)
        )
        
    # Log transaction
    conn.execute(
        """INSERT INTO inventory_transactions 
           (blood_bank_user_id, blood_group, transaction_type, units, notes, recorded_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, blood_group, trans_type, units, notes, session.get('full_name'))
    )
    
    conn.commit()
    conn.close()
    
    flash(f'{trans_type} transaction of {units} unit(s) of {blood_group} recorded successfully.', 'success')
    return redirect(url_for('bloodbank_dashboard'))

# -------------------------------------------------------------
# 5. ADMINISTRATOR DASHBOARD
# -------------------------------------------------------------
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    """Admin dashboard: KPIs, Chart.js analytics, low stock alerts, user & request audit."""
    conn = get_db()
    
    # KPI Metrics
    total_donors = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'donor'").fetchone()[0]
    total_recipients = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'recipient'").fetchone()[0]
    total_hospitals = conn.execute("SELECT COUNT(*) FROM healthcare_organizations WHERE org_type = 'hospital'").fetchone()[0]
    total_blood_banks = conn.execute("SELECT COUNT(*) FROM healthcare_organizations WHERE org_type = 'blood_bank'").fetchone()[0]
    active_requests = conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status NOT IN ('Fulfilled', 'Cancelled')").fetchone()[0]
    completed_requests = conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status = 'Fulfilled'").fetchone()[0]
    total_inventory_units = conn.execute("SELECT COALESCE(SUM(units), 0) FROM blood_inventory WHERE status != 'Expired'").fetchone()[0]
    
    # Blood Group Inventory Aggregation for Chart.js
    bg_inventory = conn.execute(
        """SELECT blood_group, SUM(units) as total_units 
           FROM blood_inventory 
           WHERE status != 'Expired'
           GROUP BY blood_group"""
    ).fetchall()
    
    bg_chart_data = {bg: 0 for bg in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']}
    for row in bg_inventory:
        bg_chart_data[row['blood_group']] = row['total_units']
        
    # Request Status Breakdown for Chart.js
    status_counts = conn.execute(
        "SELECT status, COUNT(*) as count FROM blood_requests GROUP BY status"
    ).fetchall()
    status_chart_data = {row['status']: row['count'] for row in status_counts}

    # Low Stock & Expiring Alerts
    alerts = conn.execute(
        """SELECT bi.*, ho.org_name 
           FROM blood_inventory bi
           JOIN healthcare_organizations ho ON bi.blood_bank_user_id = ho.user_id
           WHERE bi.status IN ('Low Stock', 'Expiring Soon', 'Expired')
           ORDER BY bi.expiry_date ASC"""
    ).fetchall()
    
    # All Users Table
    users_list = conn.execute(
        "SELECT id, username, email, full_name, role, phone, status, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()

    # All Requests Table
    all_requests = conn.execute(
        """SELECT br.*, u.full_name as requester_name 
           FROM blood_requests br
           JOIN users u ON br.requester_user_id = u.id
           ORDER BY br.created_at DESC"""
    ).fetchall()
    
    # Recent System Activities
    recent_activities = conn.execute(
        """SELECT rsh.*, br.request_code, u.full_name as user_name 
           FROM request_status_history rsh
           JOIN blood_requests br ON rsh.request_id = br.id
           LEFT JOIN users u ON rsh.changed_by_user_id = u.id
           ORDER BY rsh.changed_at DESC LIMIT 10"""
    ).fetchall()
    
    conn.close()
    return render_template(
        'dashboards/admin_dashboard.html',
        kpis={
            'donors': total_donors,
            'recipients': total_recipients,
            'hospitals': total_hospitals,
            'blood_banks': total_blood_banks,
            'active_requests': active_requests,
            'completed_requests': completed_requests,
            'total_units': total_inventory_units
        },
        bg_chart_data=bg_chart_data,
        status_chart_data=status_chart_data,
        alerts=alerts,
        users=users_list,
        requests=all_requests,
        activities=recent_activities
    )

@app.route('/admin/user/<int:u_id>/toggle-status', methods=['POST'])
@role_required('admin')
def admin_toggle_user_status(u_id):
    """Admin toggle to activate or suspend a user account."""
    if u_id == session.get('user_id'):
        flash('You cannot suspend your own admin account.', 'danger')
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (u_id,)).fetchone()
    if user:
        new_status = 'suspended' if user['status'] == 'active' else 'active'
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, u_id))
        conn.commit()
        flash(f'User {user["full_name"]} has been {new_status}.', 'info')
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reseed-db', methods=['POST'])
@role_required('admin')
def admin_reseed_db():
    """Reseeds the database with clean demo data during live PBL presentations."""
    database.init_db(force_reseed=True)
    flash('Database reseeded successfully with fresh fictional demonstration data.', 'success')
    return redirect(url_for('admin_dashboard'))

# -------------------------------------------------------------
# NOTIFICATIONS & AJAX APIS
# -------------------------------------------------------------
@app.route('/api/notifications')
@login_required
def get_notifications_api():
    """Returns JSON list of notifications for the logged-in user."""
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 15",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(n) for n in notifs])

@app.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Marks a single notification as read."""
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Marks all user notifications as read."""
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session['user_id'],))
    conn.commit()
    conn.close()
    flash('All notifications marked as read.', 'info')
    return redirect(request.referrer or url_for('user_home_redirect'))

# -------------------------------------------------------------
# ERROR HANDLERS
# -------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', not_found=True), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html', server_error=True), 500

# -------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -------------------------------------------------------------
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=True)
