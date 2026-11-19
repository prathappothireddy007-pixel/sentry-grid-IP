"""
SentryGrid – Comprehensive Enhanced Capstone Feature Test Suite
================================================================
Verifies all newly integrated capstone modules:
1. USGS Live Earthquake Feed & Explainable Severity Engine
2. Multi-Hazard Composite Risk Evaluator
3. Missing Persons Management Lifecycle & Privacy Masking
4. Dedicated Hospitals Directory & OSRM Polyline Routing
5. Intelligent Heuristic Rescue Team Recommendation Engine
6. Relief Resource Allocations & Stock Movement Audit Ledger
7. User Profile Management & Settings
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def login_session(client, user_id=1, role='admin', username='admin'):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['role'] = role
        sess['username'] = username
        sess['full_name'] = f"Test {role.title()}"
        sess['locality'] = 'Chennai'


# ============================================================
# 1. USGS LIVE EARTHQUAKE FEED
# ============================================================
def test_earthquakes_live_api(client):
    login_session(client, role='admin')
    res = client.get('/api/earthquakes?period=day&min_magnitude=4.5')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'features' in data
    assert isinstance(data['features'], list)
    if len(data['features']) > 0:
        f = data['features'][0]
        assert 'magnitude' in f
        assert 'place' in f
        assert 'severity' in f
        assert 'url' in f
        assert f['severity'] in ['Low', 'Medium', 'High', 'Critical']


# ============================================================
# 2. MULTI-HAZARD COMPOSITE RISK ENGINE
# ============================================================
def test_evaluate_risk_engine(client):
    login_session(client, role='admin')
    # Test safe conditions
    res = client.get('/api/alerts/evaluate-risk?wind_speed=20&rainfall_rate=10&temperature=30')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['severity'] in ['Low', 'Medium', 'High', 'Critical']

    # Test extreme flood/cyclone conditions triggering critical
    res_crit = client.get('/api/alerts/evaluate-risk?wind_speed=95&rainfall_rate=120&temperature=32')
    assert res_crit.status_code == 200
    crit_data = res_crit.get_json()
    assert crit_data['severity'] == 'Critical'
    assert len(crit_data['breached_rules']) >= 2


# ============================================================
# 3. MISSING PERSONS LIFECYCLE & PRIVACY MASKING
# ============================================================
def test_missing_persons_privacy_masking(client):
    # Citizen view should mask contact telephone
    login_session(client, user_id=999, role='citizen', username='citizen_test')
    res_cit = client.get('/api/missing-persons')
    assert res_cit.status_code == 200
    cit_data = res_cit.get_json()
    assert cit_data['success'] is True
    assert len(cit_data['data']) > 0
    first_case = cit_data['data'][0]
    phone = first_case.get('contact_phone', '')
    if phone and len(phone) >= 7:
        assert '*' in phone

    # Admin view should receive unmasked contact telephone
    login_session(client, user_id=1, role='admin', username='admin')
    res_adm = client.get('/api/missing-persons')
    assert res_adm.status_code == 200
    adm_data = res_adm.get_json()
    adm_case = adm_data['data'][0]
    adm_phone = adm_case.get('contact_phone', '')
    if adm_phone:
        assert '*' not in adm_phone


def test_missing_persons_case_creation_and_stats(client):
    login_session(client, role='admin')
    # Stats endpoint
    res_stats = client.get('/api/missing-persons/stats')
    assert res_stats.status_code == 200
    sdata = res_stats.get_json()
    assert sdata['success'] is True
    assert 'total' in sdata['data']

    # Creation
    payload = {
        'full_name': 'Automated Test Individual',
        'age': 32,
        'gender': 'Male',
        'last_seen_location': 'Velachery Main Road, Chennai',
        'last_seen_date': '2026-11-19 14:00:00',
        'description': 'Wearing blue shirt during flood evacuation.',
        'contact_name': 'Emergency Contact',
        'contact_phone': '9876543210',
        'latitude': 12.9815,
        'longitude': 80.2180
    }
    res_create = client.post('/api/missing-persons', json=payload)
    assert res_create.status_code == 201
    cdata = res_create.get_json()
    assert cdata['success'] is True
    assert cdata['data']['case_number'].startswith('MP-2026-')
    created_id = cdata['data']['id']

    # Update status to Located
    res_status = client.put(f'/api/missing-persons/{created_id}/status', json={'status': 'Located'})
    assert res_status.status_code == 200
    assert res_status.get_json()['success'] is True


# ============================================================
# 4. HOSPITALS DIRECTORY & OSRM ROUTING
# ============================================================
def test_hospitals_directory_and_routing(client):
    login_session(client, role='admin')
    # List hospitals
    res = client.get('/api/hospitals?user_lat=13.0827&user_lon=80.2707')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['data']) > 0
    hosp = data['data'][0]
    assert 'distance_km' in hosp
    assert 'total_beds' in hosp
    assert 'available_beds' in hosp

    # Routing endpoint
    res_route = client.get('/api/route?start_lat=13.0827&start_lon=80.2707&end_lat=13.0500&end_lon=80.2824')
    assert res_route.status_code == 200
    rdata = res_route.get_json()
    assert rdata['success'] is True
    assert 'coordinates' in rdata['data']
    assert len(rdata['data']['coordinates']) >= 2
    assert 'distance_km' in rdata['data']
    assert 'safety_advisory' in rdata['data']


# ============================================================
# 5. SMART HEURISTIC RESCUE SQUAD RECOMMENDATION
# ============================================================
def test_recommend_teams_engine(client):
    login_session(client, role='admin')
    res = client.get('/api/requests/1/recommend-teams')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'incident' in data
    assert data['incident']['tracking_code'].startswith('SG-2026-')
    assert len(data['data']) > 0

    top_team = data['data'][0]
    assert 'recommendation_score' in top_team
    assert 'reasons' in top_team
    assert isinstance(top_team['reasons'], list)
    assert top_team['recommendation_score'] >= 50


# ============================================================
# 6. RELIEF INVENTORY ALLOCATION & AUDIT LEDGER
# ============================================================
def test_resource_allocation_and_movements(client):
    login_session(client, role='admin')
    # Check current movements
    res_m = client.get('/api/resources/movements')
    assert res_m.status_code == 200
    mdata = res_m.get_json()
    assert mdata['success'] is True
    initial_count = len(mdata['data'])

    # Test allocation
    alloc_payload = {
        'quantity': 2,
        'destination_type': 'shelter',
        'destination_id': 1,
        'notes': 'Automated unit test dispatch'
    }
    res_alloc = client.post('/api/resources/1/allocate', json=alloc_payload)
    assert res_alloc.status_code == 200
    adata = res_alloc.get_json()
    assert adata['success'] is True
    assert adata['data']['allocated_quantity'] == 2

    # Verify audit ledger recorded the movement
    res_m2 = client.get('/api/resources/movements')
    assert res_m2.status_code == 200
    assert len(res_m2.get_json()['data']) == initial_count + 1

    # Test negative balance prevention (attempting to allocate more than available)
    res_excess = client.post('/api/resources/1/allocate', json={'quantity': 999999})
    assert res_excess.status_code == 400
    assert 'Insufficient stock' in res_excess.get_json()['message']


# ============================================================
# 7. USER PROFILE MANAGEMENT
# ============================================================
def test_user_profile_get_and_update(client):
    login_session(client, user_id=1, role='admin', username='admin')
    # GET profile
    res_get = client.get('/api/profile')
    assert res_get.status_code == 200
    pdata = res_get.get_json()
    assert pdata['success'] is True
    assert pdata['data']['username'] == 'admin'

    # PUT profile
    update_payload = {
        'full_name': 'Chief Administrator',
        'phone': '+91 9999988888',
        'locality': 'Chennai Metro Command'
    }
    res_put = client.put('/api/profile', json=update_payload)
    assert res_put.status_code == 200
    assert res_put.get_json()['success'] is True
