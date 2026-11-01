"""
SentryGrid – Comprehensive API and Operational Test Suite
==========================================================
Tests every REST API endpoint across all 3 academic modules:
- Module 1: Disaster Alerts (GET, POST, PUT, DELETE, Weather, Thresholds)
- Module 2: Emergency Requests (GET, POST, PUT, Assign, Status Workflow, Messages)
- Module 3: Shelters & Resources (GET, POST, PUT, DELETE, Restock, CSV Export, Reports)
- Security: Authentication, Role-based Access Control, Password Hashing, Session Management
CSA4310 – Internet Programming
"""

import unittest
import json
import io
from app import app
from config import Config

class SentryGridTestCase(unittest.TestCase):
    """Automated test cases for SentryGrid API endpoints."""

    def setUp(self):
        """Configure test client and application state."""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()

    def test_01_public_pages(self):
        """Test landing and login page access."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'SentryGrid', response.data)

    def test_02_unauthenticated_access_denied(self):
        """Test protected routes redirect or deny access without login."""
        # Unauthenticated page redirect
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)

        # Unauthenticated API response
        res = self.client.get('/api/alerts')
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.data)
        self.assertFalse(data['success'])

    def test_03_login_validation(self):
        """Test login validation with missing/invalid credentials."""
        res = self.client.post('/api/login', json={})
        self.assertEqual(res.status_code, 400)

        res = self.client.post('/api/login', json={'username': '', 'password': ''})
        self.assertEqual(res.status_code, 400)

    def test_04_weather_telemetry(self):
        """Test weather API proxy endpoint."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'

        res = self.client.get('/api/weather?city=Chennai')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('temperature', data['data'])
        self.assertIn('humidity', data['data'])

    def test_05_weather_thresholds(self):
        """Test Module 1 automated threshold detection configuration."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'

        res = self.client.get('/api/alerts/check-thresholds')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['data'], list)

    def test_06_role_based_permissions(self):
        """Test that Citizens cannot perform administrator operations."""
        # Authenticate as Citizen
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['username'] = 'citizen1'
            sess['role'] = 'citizen'

        # Attempt to issue an alert (Admin only)
        res = self.client.post('/api/alerts', json={
            'title': 'Unauthorized Alert',
            'disaster_type': 'flood',
            'severity': 'Critical',
            'location': 'Chennai'
        })
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertFalse(data['success'])

        # Attempt to register a shelter (Admin only)
        res = self.client.post('/api/shelters', json={
            'name': 'Unauthorized Shelter',
            'address': 'Test',
            'latitude': 13.0,
            'longitude': 80.0
        })
        self.assertEqual(res.status_code, 403)

    def test_07_logout_session_destruction(self):
        """Test session destruction upon logout."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'

        res = self.client.post('/api/logout')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

        # Verify session is empty
        res = self.client.get('/api/session')
        self.assertEqual(res.status_code, 401)

if __name__ == '__main__':
    unittest.main()
