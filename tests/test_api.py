"""
Comprehensive Automated Test Suite for TeamBoard Backend API.

================================================================================
INTERVIEW PERSPECTIVE: TEST ARCHITECTURE & BEST PRACTICES
================================================================================
1. Why APITestCase over TestCase?
   - `rest_framework.test.APITestCase` extends Django's standard TestCase.
   - It provides `self.client` pre-configured with DRF's APIClient, which includes:
     * Native JSON formatting (`client.post(..., format='json')`).
     * `client.credentials(HTTP_AUTHORIZATION=...)` helper for Bearer token auth.
     * Accurate request/response inspection matching DRF parsers and renderers.

2. Test Database Isolation:
   - Django executes each test inside a database transaction and rolls back
     at the end of each test method, ensuring complete isolation and preventing
     cross-test state pollution.

3. Testing the Entire Assignment Scope (11 Core Scenarios + Edge Cases):
   - Scenario 1: POST /api/auth/register/ - 201 Created (Token + API key returned)
   - Scenario 2: POST /api/auth/register/ - 400 Bad Request (Duplicate username)
   - Scenario 3: POST /api/auth/register/ - 400 Bad Request (Missing/blank fields)
   - Scenario 4: POST /api/auth/login/ - 200 OK (Token + API key + company_name returned)
   - Scenario 5: POST /api/auth/login/ - 401 Unauthorized (Invalid password / username)
   - Scenario 6: POST /api/kb/query/ - 401 Unauthorized (Missing Bearer token)
   - Scenario 7: POST /api/kb/query/ - 200 OK (Matches found, QueryLog written)
   - Scenario 8: POST /api/kb/query/ - 200 OK (Zero matches found, QueryLog STILL written)
   - Scenario 9: POST /api/kb/query/ - 400 Bad Request (Missing or blank search term)
   - Scenario 10: GET /api/admin/usage-summary/ - 403 Forbidden (CLIENT role attempting admin access)
   - Scenario 11: GET /api/admin/usage-summary/ - 200 OK (ADMIN role with accurate aggregations)
   - Signal Verification: Company profile and API key auto-generation via post_save signal
   - Security: Payload role tampering rejection (CLIENT role always enforced)
================================================================================
"""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Company, KBEntry, QueryLog


class TeamBoardBaseTestCase(APITestCase):
    """
    Base test case providing reusable helpers and fixtures.
    """

    def setUp(self):
        # Seed standard KB entries for testing
        self.kb_entry_1 = KBEntry.objects.create(
            question="What is select_related in Django ORM?",
            answer="select_related performs a SQL JOIN and fetches related single-object relationships.",
            category=KBEntry.Category.DATABASE
        )
        self.kb_entry_2 = KBEntry.objects.create(
            question="How does transaction.atomic() work in Django?",
            answer="transaction.atomic() provides ACID transaction guarantees in database operations.",
            category=KBEntry.Category.DATABASE
        )
        self.kb_entry_3 = KBEntry.objects.create(
            question="What is a JWT token and stateless auth?",
            answer="A JSON Web Token consists of Header, Payload, and Signature for stateless authentication.",
            category=KBEntry.Category.API
        )
        self.kb_entry_4 = KBEntry.objects.create(
            question="When should I use Q objects in Django queries?",
            answer="Q objects encapsulate complex SQL conditions like OR (|) and NOT (~).",
            category=KBEntry.Category.FRAMEWORK
        )

    def create_user_and_company(self, username, password, company_name, email, role=Company.Role.CLIENT):
        """
        Helper to create a user, let the signal create the company,
        and optionally configure role and company name.
        """
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email
        )
        # Signal will have auto-created user.company
        company = user.company
        company.company_name = company_name
        company.role = role
        company.save(update_fields=['company_name', 'role'])
        return user, company

    def get_jwt_token(self, user):
        """
        Helper to generate an access token for a given user.
        """
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)


class RegistrationEndpointTests(TeamBoardBaseTestCase):
    """
    Tests for POST /api/auth/register/
    """

    def setUp(self):
        super().setUp()
        self.register_url = reverse('api-auth-register')

    def test_scenario_1_registration_success(self):
        """
        Scenario 1: Successful registration returns 201, JWT access token, and auto-generated API key.
        """
        payload = {
            "username": "acmecorp",
            "password": "securepass123",
            "company_name": "Acme Corp",
            "email": "dev@acmecorp.com"
        }
        response = self.client.post(self.register_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'], "acmecorp")
        self.assertEqual(response.data['company_name'], "Acme Corp")
        self.assertIn('api_key', response.data)
        self.assertIn('access', response.data)
        self.assertTrue(len(response.data['api_key']) >= 32)
        self.assertTrue(len(response.data['access']) > 20)

        # Verify DB state
        user = User.objects.get(username="acmecorp")
        self.assertEqual(user.email, "dev@acmecorp.com")
        self.assertTrue(user.check_password("securepass123"))

        # Verify company profile created by signal
        self.assertTrue(hasattr(user, 'company'))
        company = user.company
        self.assertEqual(company.company_name, "Acme Corp")
        self.assertEqual(company.role, Company.Role.CLIENT)
        self.assertEqual(company.api_key, response.data['api_key'])

    def test_scenario_2_registration_duplicate_username(self):
        """
        Scenario 2: Registration returns 400 when username already exists.
        """
        # Register first user
        self.create_user_and_company(
            username="existinguser",
            password="password123",
            company_name="First Corp",
            email="first@corp.com"
        )

        payload = {
            "username": "existinguser",
            "password": "newpassword456",
            "company_name": "Second Corp",
            "email": "second@corp.com"
        }
        response = self.client.post(self.register_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_scenario_3_registration_missing_or_blank_fields(self):
        """
        Scenario 3: Registration returns 400 when required fields are missing or empty.
        """
        # Missing password and company_name
        invalid_payload = {
            "username": "missingfields",
            "email": "missing@example.com"
        }
        response = self.client.post(self.register_url, invalid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertIn('company_name', response.data)

        # Blank username
        blank_username_payload = {
            "username": "   ",
            "password": "validpassword",
            "company_name": "Valid Corp",
            "email": "test@example.com"
        }
        response = self.client.post(self.register_url, blank_username_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_ignores_tampered_role(self):
        """
        Security requirement: role must always default to CLIENT, never accept role from payload.
        """
        payload = {
            "username": "hacker_corp",
            "password": "secretpassword",
            "company_name": "Hacker Corp",
            "email": "hacker@example.com",
            "role": "admin"  # Malicious attempt to self-escalate to admin
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="hacker_corp")
        self.assertEqual(user.company.role, Company.Role.CLIENT)


class LoginEndpointTests(TeamBoardBaseTestCase):
    """
    Tests for POST /api/auth/login/
    """

    def setUp(self):
        super().setUp()
        self.login_url = reverse('api-auth-login')
        self.user, self.company = self.create_user_and_company(
            username="logintestuser",
            password="validpassword123",
            company_name="Login Test Corp",
            email="login@testcorp.com"
        )

    def test_scenario_4_login_success(self):
        """
        Scenario 4: Login returns 200 with JWT access token, company_name, and api_key.
        """
        payload = {
            "username": "logintestuser",
            "password": "validpassword123"
        }
        response = self.client.post(self.login_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['company_name'], "Login Test Corp")
        self.assertEqual(response.data['api_key'], self.company.api_key)

    def test_scenario_5_login_invalid_credentials(self):
        """
        Scenario 5: Login returns 401 with clear error message when password or username is wrong.
        """
        # Wrong password
        payload_wrong_pw = {
            "username": "logintestuser",
            "password": "wrongpassword"
        }
        response = self.client.post(self.login_url, payload_wrong_pw, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)

        # Nonexistent username
        payload_no_user = {
            "username": "ghostuser",
            "password": "validpassword123"
        }
        response = self.client.post(self.login_url, payload_no_user, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)


class KBQueryEndpointTests(TeamBoardBaseTestCase):
    """
    Tests for POST /api/kb/query/
    """

    def setUp(self):
        super().setUp()
        self.query_url = reverse('api-kb-query')
        self.user, self.company = self.create_user_and_company(
            username="clientcompany",
            password="password123",
            company_name="Query Client Corp",
            email="client@query.com"
        )
        self.token = self.get_jwt_token(self.user)

    def test_scenario_6_kb_query_unauthenticated(self):
        """
        Scenario 6: Querying without a valid token returns 401 Unauthorized.
        """
        response = self.client.post(self.query_url, {"search": "select_related"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_scenario_7_kb_query_matching_results(self):
        """
        Scenario 7: Authenticated search returns matching KB records, accurate count, and creates QueryLog.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        payload = {"search": "select_related"}
        response = self.client.post(self.query_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['search'], "select_related")
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['question'], self.kb_entry_1.question)

        # Verify QueryLog was recorded in DB
        log = QueryLog.objects.filter(company=self.company).latest('queried_at')
        self.assertEqual(log.search_term, "select_related")
        self.assertEqual(log.results_count, 1)

    def test_scenario_8_kb_query_zero_results(self):
        """
        Scenario 8: Search with zero matches returns 200, count: 0, results: [], and STILL writes QueryLog.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        payload = {"search": "completely_unmatched_term_xyz_123"}
        response = self.client.post(self.query_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])

        # Crucial requirement: QueryLog MUST be written even when count is 0 for billing
        log = QueryLog.objects.filter(company=self.company, search_term="completely_unmatched_term_xyz_123").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.results_count, 0)

    def test_scenario_9_kb_query_missing_or_blank_search_term(self):
        """
        Scenario 9: Returns 400 when search field is missing or contains only whitespace.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # Missing field
        response_missing = self.client.post(self.query_url, {}, format='json')
        self.assertEqual(response_missing.status_code, status.HTTP_400_BAD_REQUEST)

        # Blank string
        response_blank = self.client.post(self.query_url, {"search": "   "}, format='json')
        self.assertEqual(response_blank.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kb_query_case_insensitivity(self):
        """
        Verifies case-insensitive search across question and answer using Q objects + icontains.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # Lowercase
        res_lower = self.client.post(self.query_url, {"search": "transaction.atomic"}, format='json')
        # Uppercase
        res_upper = self.client.post(self.query_url, {"search": "TRANSACTION.ATOMIC"}, format='json')

        self.assertEqual(res_lower.status_code, status.HTTP_200_OK)
        self.assertEqual(res_upper.status_code, status.HTTP_200_OK)
        self.assertEqual(res_lower.data['count'], res_upper.data['count'])
        self.assertTrue(res_lower.data['count'] >= 1)


class AdminUsageSummaryEndpointTests(TeamBoardBaseTestCase):
    """
    Tests for GET /api/admin/usage-summary/
    """

    def setUp(self):
        super().setUp()
        self.admin_summary_url = reverse('api-admin-usage-summary')

        # Create Client user
        self.client_user, self.client_company = self.create_user_and_company(
            username="regular_client",
            password="password123",
            company_name="Regular Client Inc",
            email="client@inc.com",
            role=Company.Role.CLIENT
        )
        self.client_token = self.get_jwt_token(self.client_user)

        # Create Admin user
        self.admin_user, self.admin_company = self.create_user_and_company(
            username="platform_admin",
            password="password123",
            company_name="Platform Admin HQ",
            email="admin@platform.com",
            role=Company.Role.ADMIN
        )
        self.admin_token = self.get_jwt_token(self.admin_user)

    def test_scenario_10_admin_summary_client_forbidden(self):
        """
        Scenario 10: Regular CLIENT role attempting to access admin summary receives 403 Forbidden.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client_token}')
        response = self.client.get(self.admin_summary_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_summary_unauthenticated(self):
        """
        Unauthenticated request receives 401 Unauthorized.
        """
        response = self.client.get(self.admin_summary_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_scenario_11_admin_summary_success_and_aggregations(self):
        """
        Scenario 11: ADMIN role receives 200 with total_queries, active_companies, and top 5 search terms.
        """
        # Create a second company for multi-company analytics
        user_2, company_2 = self.create_user_and_company(
            username="beta_client",
            password="password123",
            company_name="Beta Client LLC",
            email="beta@client.com",
            role=Company.Role.CLIENT
        )

        # Seed sample query logs with known frequencies:
        # "select_related": 3 queries
        # "transaction atomic": 2 queries
        # "Q objects": 1 query
        QueryLog.objects.create(company=self.client_company, search_term="select_related", results_count=2)
        QueryLog.objects.create(company=self.client_company, search_term="select_related", results_count=2)
        QueryLog.objects.create(company=company_2, search_term="select_related", results_count=2)

        QueryLog.objects.create(company=self.client_company, search_term="transaction atomic", results_count=1)
        QueryLog.objects.create(company=company_2, search_term="transaction atomic", results_count=1)

        QueryLog.objects.create(company=company_2, search_term="Q objects", results_count=1)

        # Authenticate as admin
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_token}')
        response = self.client.get(self.admin_summary_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_queries'], 6)
        self.assertEqual(response.data['active_companies'], 2)

        top_terms = response.data['top_search_terms']
        self.assertEqual(len(top_terms), 3)
        self.assertEqual(top_terms[0]['search_term'], "select_related")
        self.assertEqual(top_terms[0]['count'], 3)
        self.assertEqual(top_terms[1]['search_term'], "transaction atomic")
        self.assertEqual(top_terms[1]['count'], 2)
        self.assertEqual(top_terms[2]['search_term'], "Q objects")
        self.assertEqual(top_terms[2]['count'], 1)


class SignalAndIntegrityTests(TeamBoardBaseTestCase):
    """
    Tests directly verifying post_save signal behavior and database integrity.
    """

    def test_signal_auto_creates_company_and_api_key(self):
        """
        Verifies that creating a User row via ORM automatically creates a Company profile
        with an auto-generated API key via post_save signal.
        """
        new_user = User.objects.create_user(
            username="signal_test_user",
            email="signal@example.com",
            password="secretpassword"
        )
        self.assertTrue(hasattr(new_user, 'company'))
        company = new_user.company
        self.assertEqual(company.user, new_user)
        self.assertEqual(company.role, Company.Role.CLIENT)
        self.assertTrue(len(company.api_key) >= 32)

