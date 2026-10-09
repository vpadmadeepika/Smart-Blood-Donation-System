"""
Smart Blood Donor Matching Engine
Algorithmic compatibility, distance ranking, and suitability analysis for blood donation requests.
"""

import math
from datetime import datetime, date

# ABO and Rh Red-Cell Compatibility Matrix
# Maps Recipient Blood Group -> List of Compatible Donor Blood Groups
COMPATIBILITY_RECIPIENT_MAP = {
    'O-': ['O-'],
    'O+': ['O-', 'O+'],
    'A-': ['O-', 'A-'],
    'A+': ['O-', 'O+', 'A-', 'A+'],
    'B-': ['O-', 'B-'],
    'B+': ['O-', 'O+', 'B-', 'B+'],
    'AB-': ['O-', 'A-', 'B-', 'AB-'],
    'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
}

# Maps Donor Blood Group -> List of Recipient Blood Groups they can donate Red Cells to
COMPATIBILITY_DONOR_MAP = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],  # Universal Red-Cell Donor
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+']  # Universal Red-Cell Recipient donor to AB+ only
}

# Standard Demo City Area Coordinates for realistic distance calculation
DEMO_AREA_COORDINATES = {
    'Downtown': (40.7128, -74.0060),
    'Medical District': (40.7180, -73.9980),
    'Westside': (40.7250, -74.0150),
    'North City': (40.7450, -73.9900),
    'South District': (40.7000, -74.0100),
    'East Hills': (40.7300, -73.9750),
    'Tech Park': (40.7500, -74.0050),
    'Riverside': (40.7350, -74.0200),
    'Central Plaza': (40.7150, -74.0000),
    'Suburban Greens': (40.7600, -73.9600)
}

def get_compatible_donor_groups(recipient_group: str) -> list:
    """Returns the list of compatible blood groups for a given recipient."""
    return COMPATIBILITY_RECIPIENT_MAP.get(recipient_group.strip().upper(), [])

def is_compatible(donor_group: str, recipient_group: str) -> bool:
    """Checks if donor blood group is red-cell compatible with recipient blood group."""
    compatible_groups = get_compatible_donor_groups(recipient_group)
    return donor_group.strip().upper() in compatible_groups

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two geographic points in kilometers."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 5.0  # default reasonable distance if coordinates unavailable
    
    R = 6371.0  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return round(distance, 1)

def estimate_area_distance(area1: str, area2: str, lat1=None, lon1=None, lat2=None, lon2=None) -> float:
    """Estimates distance using coordinates if provided, otherwise looks up area coordinates."""
    if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
        return calculate_haversine_distance(lat1, lon1, lat2, lon2)
    
    coord1 = DEMO_AREA_COORDINATES.get(area1, (40.7128, -74.0060))
    coord2 = DEMO_AREA_COORDINATES.get(area2, (40.7200, -74.0000))
    
    return calculate_haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])

def evaluate_donation_cooldown(last_donation_date) -> tuple:
    """
    Evaluates donor rest period.
    Standard recommendation: 90 days (12 weeks) between whole blood donations.
    Returns: (is_eligible_by_interval: bool, days_since: int, message: str)
    """
    if not last_donation_date:
        return (True, 999, "First-time or unrecorded donor. Standard health screening required.")
    
    if isinstance(last_donation_date, str):
        try:
            last_date = datetime.strptime(last_donation_date, "%Y-%m-%d").date()
        except ValueError:
            return (True, 999, "Last donation date recorded.")
    elif isinstance(last_donation_date, datetime):
        last_date = last_donation_date.date()
    else:
        last_date = last_donation_date
        
    days = (date.today() - last_date).days
    
    if days >= 90:
        return (True, days, f"Last donated {days} days ago (meets typical 90-day recovery interval).")
    elif days >= 60:
        return (False, days, f"Donated {days} days ago (within 60-89 day window; requires medical clearance).")
    else:
        return (False, days, f"Recent donation {days} days ago (in recovery cooldown).")

def rank_donors_for_request(request_data: dict, donor_list: list) -> list:
    """
    Ranks potential donors for a blood request based on:
    1. Blood Group Compatibility (Exact match > Compatible match)
    2. Proximity / Estimated Distance
    3. Availability Status
    4. Donation History & Cooldown
    5. Contact Consent
    
    Returns a sorted list of donor dictionaries with match scores, distance, and explanation badges.
    """
    req_bg = request_data.get('blood_group', 'O+')
    req_lat = request_data.get('latitude')
    req_lon = request_data.get('longitude')
    req_area = request_data.get('area', 'Downtown')
    req_city = request_data.get('city', 'Metro City')

    compatible_groups = get_compatible_donor_groups(req_bg)
    ranked = []

    for donor in donor_list:
        d_bg = donor.get('blood_group', '')
        if d_bg not in compatible_groups:
            continue  # Skip strictly incompatible blood groups

        # 1. Base Compatibility Score
        is_exact = (d_bg == req_bg)
        compat_score = 50.0 if is_exact else 35.0
        
        # 2. Distance Calculation
        d_lat = donor.get('latitude')
        d_lon = donor.get('longitude')
        d_area = donor.get('area', '')
        distance_km = estimate_area_distance(req_area, d_area, req_lat, req_lon, d_lat, d_lon)
        
        # Distance score: Max 30 points (decreases with distance)
        # 0 km = 30 pts, 10 km = 20 pts, 30+ km = 5 pts
        dist_score = max(5.0, 30.0 - (distance_km * 0.8))
        
        # 3. Availability Score (Max 15 points)
        is_avail = bool(donor.get('is_available', 1))
        avail_score = 15.0 if is_avail else 0.0
        
        # 4. Donation Cooldown (Max 10 points)
        eligible_interval, days_since, interval_msg = evaluate_donation_cooldown(donor.get('last_donation_date'))
        interval_score = 10.0 if eligible_interval else 2.0
        
        # Total composite score (out of 100)
        total_score = min(100.0, round(compat_score + dist_score + avail_score + interval_score, 1))

        # Generate Detailed Explanation
        explanations = []
        if is_exact:
            explanations.append(f"Exact match ({d_bg})")
        else:
            explanations.append(f"Compatible donor group ({d_bg} → {req_bg})")
            
        explanations.append(f"{distance_km} km away in {d_area or 'area'}")
        
        if is_avail:
            explanations.append("Marked Available")
        else:
            explanations.append("Currently Marked Busy")
            
        explanations.append(interval_msg)

        donor_match_item = {
            'donor_user_id': donor.get('user_id') or donor.get('id'),
            'full_name': donor.get('full_name', 'Anonymous Donor'),
            'phone': donor.get('phone', 'N/A'),
            'email': donor.get('email', 'N/A'),
            'blood_group': d_bg,
            'age': donor.get('age'),
            'gender': donor.get('gender', 'Not specified'),
            'city': donor.get('city', req_city),
            'area': d_area,
            'distance_km': distance_km,
            'is_available': is_avail,
            'is_exact_match': is_exact,
            'compatibility_score': total_score,
            'last_donation_date': donor.get('last_donation_date'),
            'interval_message': interval_msg,
            'explanation': " • ".join(explanations),
            'consent_contact': bool(donor.get('consent_contact', 1)),
            'total_donations': donor.get('total_donations', 0)
        }
        ranked.append(donor_match_item)

    # Sort by compatibility score descending, then distance ascending
    ranked.sort(key=lambda x: (-x['compatibility_score'], x['distance_km']))
    return ranked
