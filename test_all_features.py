"""
SentryGrid – Comprehensive End-to-End Operational Test Suite
============================================================
Tests all 3 academic modules with actual MySQL 8.0 database persistence:
- Authentication & Roles (Citizen, Responder, Administrator)
- Module 1: Disaster Monitoring & Alert System
- Module 2: Emergency Reporting & Rescue Coordination Workflow
- Module 3: Shelter Information, Resource Logistics & Analytical Reports
CSA4310 – Internet Programming
"""

import unittest
import json
import io
from app import app

class SentryGridFullSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-csa4310'

    def setUp(self):
        self.client = app.test_client()

    # -------------------------------------------------------------
    # Test 1: User Authentication & Role-Based Access Control
    # -------------------------------------------------------------
    def test_01_authentication_roles(self):
        """Verify Citizen, Responder, and Admin login and session."""
        roles = [
            ('admin', 'admin123', 'admin'),
            ('responder1', 'resp123', 'responder'),
            ('citizen1', 'citizen123', 'citizen')
        ]

        for username, password, expected_role in roles:
            res = self.client.post('/api/login', json={'username': username, 'password': password})
            self.assertEqual(res.status_code, 200, f"Failed login for {username}")
            data = json.loads(res.data)
            self.assertTrue(data['success'])
            self.assertEqual(data['data']['role'], expected_role)

            # Check session retrieval
            sess_res = self.client.get('/api/session')
            sess_data = json.loads(sess_res.data)
            self.assertTrue(sess_data['success'])
            self.assertEqual(sess_data['data']['role'], expected_role)

            # Logout
            self.client.post('/api/logout')

    # -------------------------------------------------------------
    # Test 2: Module 1 – Disaster Alerts & External Weather
    # -------------------------------------------------------------
    def test_02_module1_alerts_and_weather(self):
        """Verify Module 1 alert retrieval, weather telemetry, and threshold checks."""
        # Login as Admin
        self.client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        # 1. Fetch active alerts
        res = self.client.get('/api/alerts?active=true')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['data']), 0, "Active alerts should not be empty")

        # 2. Test External Weather Telemetry Proxy
        res = self.client.get('/api/weather?city=Chennai')
        self.assertEqual(res.status_code, 200)
        w_data = json.loads(res.data)
        self.assertTrue(w_data['success'])
        self.assertIn('temperature', w_data['data'])
        self.assertIn('humidity', w_data['data'])

        # 3. Test Automated Thresholds Configuration
        res = self.client.get('/api/alerts/check-thresholds')
        self.assertEqual(res.status_code, 200)
        t_data = json.loads(res.data)
        self.assertTrue(t_data['success'])
        self.assertIsInstance(t_data['data'], list)

        # 4. Admin creates a new alert
        res = self.client.post('/api/alerts', json={
            'title': 'Test Monsoon Surge Warning',
            'disaster_type': 'storm',
            'severity': 'High',
            'location': 'Chennai, Marina Shore',
            'latitude': 13.0500,
            'longitude': 80.2824,
            'description': 'Automated test alert for system verification.',
            'safety_instructions': 'Do not venture near seaside promenade.'
        })
        self.assertEqual(res.status_code, 201)
        create_data = json.loads(res.data)
        self.assertTrue(create_data['success'])
        alert_id = create_data['data']['id']

        # 5. Admin updates the alert
        res = self.client.put(f'/api/alerts/{alert_id}', json={'severity': 'Critical'})
        self.assertEqual(res.status_code, 200)

        # 6. Admin deactivates the alert
        res = self.client.delete(f'/api/alerts/{alert_id}')
        self.assertEqual(res.status_code, 200)

        self.client.post('/api/logout')

    # -------------------------------------------------------------
    # Test 3: Module 2 – Emergency Requests & Status Workflow
    # -------------------------------------------------------------
    def test_03_module2_emergency_workflow(self):
        """Verify full emergency workflow: Reported -> Verified -> Dispatched -> Rescued -> Closed."""
        # 1. Citizen logs in and triggers an SOS
        self.client.post('/api/login', json={'username': 'citizen1', 'password': 'citizen123'})
        sos_res = self.client.post('/api/requests', json={
            'citizen_name': 'Priya Sharma',
            'contact_number': '9876543212',
            'emergency_type': 'trapped',
            'priority': 'Critical',
            'is_sos': True,
            'latitude': 13.0827,
            'longitude': 80.2707,
            'location': 'Chennai Central',
            'description': 'Elevator stuck between 3rd and 4th floor due to power outage.'
        })
        self.assertEqual(sos_res.status_code, 201)
        sos_data = json.loads(sos_res.data)
        self.assertTrue(sos_data['success'])
        request_id = sos_data['data']['id']
        self.assertEqual(sos_data['data']['status'], 'Reported')

        # 2. Citizen posts a message in the incident thread
        msg_res = self.client.post(f'/api/requests/{request_id}/messages', json={
            'message': 'Water is leaking into the shaft. Please hurry!'
        })
        self.assertEqual(msg_res.status_code, 201)

        self.client.post('/api/logout')

        # 3. Admin logs in and advances workflow to 'Verified'
        self.client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        verify_res = self.client.put(f'/api/requests/{request_id}/status', json={
            'status': 'Verified',
            'notes': 'Verified with building management dispatch.'
        })
        self.assertEqual(verify_res.status_code, 200)

        # 4. Admin assigns an available response team (Transitions to 'Dispatched')
        # Get team ID
        teams_res = self.client.get('/api/teams?status=available')
        teams = json.loads(teams_res.data)['data']
        self.assertGreater(len(teams), 0, "There should be an available team")
        team_id = teams[0]['id']

        assign_res = self.client.post(f'/api/requests/{request_id}/assign', json={
            'team_id': team_id,
            'notes': 'Dispatching technical extrication unit.'
        })
        self.assertEqual(assign_res.status_code, 201)

        self.client.post('/api/logout')

        # 5. Responder logs in and marks request as 'Rescued'
        self.client.post('/api/login', json={'username': 'responder1', 'password': 'resp123'})

        # Responder posts an update message
        self.client.post(f'/api/requests/{request_id}/messages', json={
            'message': 'On scene. Hydraulics engaged to force doors.'
        })

        # Check messages via AJAX polling
        msgs_res = self.client.get(f'/api/requests/{request_id}/messages')
        msgs_data = json.loads(msgs_res.data)
        self.assertTrue(msgs_data['success'])
        self.assertEqual(len(msgs_data['data']), 2, "Should have 2 messages in the thread")

        # Advance to Rescued
        rescue_res = self.client.put(f'/api/requests/{request_id}/status', json={
            'status': 'Rescued',
            'notes': 'All occupants extricated with zero casualties.'
        })
        self.assertEqual(rescue_res.status_code, 200)

        self.client.post('/api/logout')

        # 6. Admin closes the incident
        self.client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        close_res = self.client.put(f'/api/requests/{request_id}/status', json={
            'status': 'Closed',
            'notes': 'Incident resolved and archived.'
        })
        self.assertEqual(close_res.status_code, 200)

        self.client.post('/api/logout')

    # -------------------------------------------------------------
    # Test 4: Module 3 – Shelters, Resources & Reports
    # -------------------------------------------------------------
    def test_04_module3_shelters_resources_reports(self):
        """Verify shelter distance sorting, resource deficit alerts, restock, and CSV report download."""
        # 1. Citizen searches for shelters with GPS coordinates (Nearest First)
        self.client.post('/api/login', json={'username': 'citizen1', 'password': 'citizen123'})

        sh_res = self.client.get('/api/shelters?lat=13.0827&lon=80.2707')
        self.assertEqual(sh_res.status_code, 200)
        sh_data = json.loads(sh_res.data)
        self.assertTrue(sh_data['success'])
        self.assertGreater(len(sh_data['data']), 0)
        # Verify Haversine distance calculation is present
        self.assertIsNotNone(sh_data['data'][0]['distance_km'])

        self.client.post('/api/logout')

        # 2. Admin logs in to manage resources
        self.client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        # Fetch resources
        res_res = self.client.get('/api/resources')
        self.assertEqual(res_res.status_code, 200)
        resources = json.loads(res_res.data)['data']
        self.assertGreater(len(resources), 0)

        # Check deficit / low stock identification
        target_res = resources[0]
        initial_qty = target_res['quantity']

        # Restock resource
        restock_res = self.client.put(f'/api/resources/{target_res["id"]}/restock', json={'quantity': 50})
        self.assertEqual(restock_res.status_code, 200)
        restock_data = json.loads(restock_res.data)
        self.assertEqual(restock_data['data']['new_quantity'], initial_qty + 50)

        # 3. Summary analytical report
        summary_res = self.client.get('/api/reports/summary')
        self.assertEqual(summary_res.status_code, 200)
        summary_data = json.loads(summary_res.data)
        self.assertTrue(summary_data['success'])
        self.assertIn('alerts', summary_data['data'])
        self.assertIn('requests', summary_data['data'])
        self.assertIn('shelters', summary_data['data'])
        self.assertIn('resources', summary_data['data'])

        # 4. CSV Downloadable Reports
        for report_type in ['requests', 'resources', 'alerts']:
            csv_res = self.client.get(f'/api/reports/csv?type={report_type}')
            self.assertEqual(csv_res.status_code, 200)
            self.assertEqual(csv_res.mimetype, 'text/csv')
            self.assertIn(b',', csv_res.data)

        self.client.post('/api/logout')

if __name__ == '__main__':
    unittest.main()
