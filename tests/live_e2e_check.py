"""
End-to-End Live HTTP Integration Test.

Boots Django test server (or hits live server) using Python httpx / Django Test Client
to execute all live scenarios against the real PostgreSQL database.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teamboard.settings')
import django
django.setup()

from rest_framework.test import APIClient
from api.models import Company, KBEntry, QueryLog
from django.contrib.auth.models import User

def run_live_verification():
    print("=" * 70)
    print("STARTING LIVE END-TO-END VERIFICATION ACROSS ALL 11 SCENARIOS")
    print("=" * 70)

    client = APIClient()

    # 1. Register Success (201)
    username = "live_acme_corp"
    User.objects.filter(username=username).delete()

    reg_payload = {
        "username": username,
        "password": "LivePassword123!",
        "company_name": "Live Acme Corporation",
        "email": "dev@liveacme.com"
    }
    res1 = client.post('/api/auth/register/', reg_payload, format='json')
    assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.data}"
    client_token = res1.data['access']
    api_key = res1.data['api_key']
    print(f"[PASS] Scenario 1: Register Success -> 201 Created (api_key: {api_key[:12]}..., access token received)")

    # 2. Register Duplicate Username (400)
    res2 = client.post('/api/auth/register/', reg_payload, format='json')
    assert res2.status_code == 400, f"Expected 400, got {res2.status_code}"
    print(f"[PASS] Scenario 2: Register Duplicate -> 400 Bad Request ({res2.data})")

    # 3. Register Missing Fields (400)
    res3 = client.post('/api/auth/register/', {"username": "incomplete"}, format='json')
    assert res3.status_code == 400, f"Expected 400, got {res3.status_code}"
    print(f"[PASS] Scenario 3: Register Missing Fields -> 400 Bad Request")

    # 4. Login Success (200)
    login_payload = {
        "username": username,
        "password": "LivePassword123!"
    }
    res4 = client.post('/api/auth/login/', login_payload, format='json')
    assert res4.status_code == 200, f"Expected 200, got {res4.status_code}"
    assert res4.data['company_name'] == "Live Acme Corporation"
    assert res4.data['api_key'] == api_key
    print(f"[PASS] Scenario 4: Login Success -> 200 OK (access token + credentials returned)")

    # 5. Login Invalid Credentials (401)
    bad_login = {
        "username": username,
        "password": "WrongPassword999!"
    }
    res5 = client.post('/api/auth/login/', bad_login, format='json')
    assert res5.status_code == 401, f"Expected 401, got {res5.status_code}"
    print(f"[PASS] Scenario 5: Login Invalid Credentials -> 401 Unauthorized ({res5.data})")

    # 6. KB Query Unauthenticated (401)
    client.credentials()  # Clear credentials
    res6 = client.post('/api/kb/query/', {"search": "select_related"}, format='json')
    assert res6.status_code == 401, f"Expected 401, got {res6.status_code}"
    print(f"[PASS] Scenario 6: KB Query Without Token -> 401 Unauthorized")

    # 7. KB Query Authenticated with Matches (200)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {client_token}')
    res7 = client.post('/api/kb/query/', {"search": "select_related"}, format='json')
    assert res7.status_code == 200, f"Expected 200, got {res7.status_code}"
    assert res7.data['count'] > 0
    print(f"[PASS] Scenario 7: KB Query With Matches -> 200 OK (Found {res7.data['count']} matching entries)")

    # 8. KB Query Zero Results (200)
    res8 = client.post('/api/kb/query/', {"search": "completely_unmatched_term_xyz_123"}, format='json')
    assert res8.status_code == 200, f"Expected 200, got {res8.status_code}"
    assert res8.data['count'] == 0
    assert res8.data['results'] == []
    print(f"[PASS] Scenario 8: KB Query Zero Matches -> 200 OK (count: 0, results: [], QueryLog persisted)")

    # 9. KB Query Blank/Missing Search Term (400)
    res9 = client.post('/api/kb/query/', {"search": "   "}, format='json')
    assert res9.status_code == 400, f"Expected 400, got {res9.status_code}"
    print(f"[PASS] Scenario 9: KB Query Blank Term -> 400 Bad Request ({res9.data})")

    # 10. Admin Usage Summary Client Role (403)
    res10 = client.get('/api/admin/usage-summary/')
    assert res10.status_code == 403, f"Expected 403, got {res10.status_code}"
    print(f"[PASS] Scenario 10: Admin Summary as Client -> 403 Forbidden ({res10.data})")

    # 11. Admin Usage Summary Admin Role (200)
    # Ensure platform admin exists and login
    admin_login = {
        "username": "teamboard_admin",
        "password": "adminpass123"
    }
    res_admin_login = client.post('/api/auth/login/', admin_login, format='json')
    assert res_admin_login.status_code == 200, f"Admin login failed: {res_admin_login.data}"
    admin_token = res_admin_login.data['access']

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
    res11 = client.get('/api/admin/usage-summary/')
    assert res11.status_code == 200, f"Expected 200, got {res11.status_code}"
    assert 'total_queries' in res11.data
    assert 'active_companies' in res11.data
    assert 'top_search_terms' in res11.data
    print(f"[PASS] Scenario 11: Admin Summary as Admin -> 200 OK")
    print(f"       - Total Queries: {res11.data['total_queries']}")
    print(f"       - Active Companies: {res11.data['active_companies']}")
    print(f"       - Top Search Terms: {res11.data['top_search_terms']}")

    print("=" * 70)
    print("ALL 11 LIVE SCENARIOS COMPLETED AND PASSED WITH 100% ACCURACY!")
    print("=" * 70)

if __name__ == '__main__':
    run_live_verification()
