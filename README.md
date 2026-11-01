# SentryGrid – Real-Time Disaster Alert & Emergency Response System

**Course:** CSA4310 – Internet Programming  
**Technology Stack:** HTML5, CSS3, Bootstrap 5, JavaScript (ES6+), jQuery 3.7, AJAX, RESTful APIs, JSON, Python Flask, MySQL 8.0, Leaflet.js, OpenStreetMap, Chart.js.

---

## 1. Project Overview

**SentryGrid** is a production-ready, full-stack disaster management and emergency coordination web application designed to connect citizens in distress with professional emergency response squads and municipal disaster management administrators.

The application adheres strictly to the curriculum of **CSA4310 – Internet Programming**, demonstrating asynchronous client-server communication via **jQuery AJAX**, external telemetry via the **Fetch API**, spatial positioning via the **HTML5 Geolocation API**, dynamic DOM manipulation, parameterized SQL security, and role-based access control.

---

## 2. The Three Core Academic Modules

### Module 1: Disaster Monitoring & Alert System
- **External Meteorological Telemetry:** Integrated weather service proxy fetching real-time ambient conditions (temperature, precipitation rate, wind velocity, atmospheric pressure, and humidity).
- **Rule-Based Danger Thresholds:** Configurable threshold engine comparing live parameters against hazard rules (e.g., rainfall rate $> 50\,\text{mm/h}$ or wind speed $> 90\,\text{km/h}$).
- **Official Alert Broadcasting:** Administrative console to create, update, filter, and deactivate disaster warnings with classification (Low, Medium, High, Critical).
- **Public Safety Protocols:** Contextual evacuation advisories and emergency directives for citizens.
- **Asynchronous Telemetry Polling:** Automated client-side polling utilizing `setInterval()` to retrieve fresh alerts without full-page reloads.

### Module 2: Emergency Reporting & Rescue Coordination
- **Instant SOS Distress Beacon:** One-touch emergency trigger that acquires the client's live latitude and longitude via the browser's `navigator.geolocation` API and submits an urgent rescue ticket.
- **Detailed Emergency Intake (FormData):** Comprehensive incident reporting supporting categories (Medical, Fire, Flood Rescue, Trapped Persons, Other) with optional photograph evidence upload handled via multipart `FormData`.
- **Life-Cycle Status Workflow:** Strictly enforced 5-stage state pipeline:
  $$\text{Reported} \longrightarrow \text{Verified} \longrightarrow \text{Dispatched} \longrightarrow \text{Rescued} \longrightarrow \text{Closed}$$
- **Response Team Deployment:** Administrative dispatch panel assigning certified units (Medical, Fire, Flood Boat Squads, USAR) to verified requests.
- **Two-Way Field Communication:** Real-time conversational message thread between citizens and first responders with 5-second asynchronous AJAX polling.
- **Spatial Incident Mapping:** Interactive Leaflet.js / OpenStreetMap canvas plotting color-coded incident coordinates.

### Module 3: Shelter Information & Disaster Reports
- **Relief Camp Logistics:** Live tracking of safe haven capacities, occupancy rates, contact warden hotlines, and available amenities (drinking water, trauma care, backup generators, sanitation).
- **Proximity Distance Calculation:** Server-side Haversine mathematical geodesic algorithm:
  $$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
  Automatically sorting shelters nearest to the citizen's GPS coordinates.
- **Turn-by-Turn Navigation:** One-click spatial routing links to Google Maps and OpenStreetMap.
- **Resource Inventory Control:** Categorized relief stockpile management (Shelter supplies, Medical kits, Food/Water rations, Heavy rescue equipment) featuring automatic deficit warnings when stock drops below minimum thresholds.
- **Analytical SITREPs & CSV Export:** Situation reporting tables and downloadable comma-separated values (CSV) reports for emergency requests, inventory ledgers, and alert histories.

---

## 3. Database Architecture (MySQL 8.0: `sentrygrid_db`)

The database is normalized across **12 relational tables** with primary keys, foreign keys, cascading rules, and audit timestamps:

| # | Table Name | Purpose | Primary Key | Foreign Keys |
|---|------------|---------|-------------|--------------|
| 1 | `users` | Accounts, hashed credentials, roles, phone, locality, coordinates | `id` | - |
| 2 | `disaster_alerts` | Disaster warning broadcasts, severities, safety instructions | `id` | `created_by` $\rightarrow$ `users(id)` |
| 3 | `emergency_requests` | SOS tickets and detailed citizen rescue reports | `id` | `user_id` $\rightarrow$ `users(id)` |
| 4 | `emergency_status_history` | Audit trail of all workflow state changes | `id` | `request_id` $\rightarrow$ `emergency_requests(id)`, `changed_by` $\rightarrow$ `users(id)` |
| 5 | `response_teams` | Specialized field units, readiness status, crew count | `id` | - |
| 6 | `team_assignments` | Linking response units to active emergency tickets | `id` | `request_id` $\rightarrow$ `emergency_requests(id)`, `team_id` $\rightarrow$ `response_teams(id)`, `assigned_by` $\rightarrow$ `users(id)` |
| 7 | `emergency_messages` | Citizen-responder field communication chat messages | `id` | `request_id` $\rightarrow$ `emergency_requests(id)`, `sender_id` $\rightarrow$ `users(id)` |
| 8 | `shelters` | Relief shelter addresses, bed capacity, occupancy, contacts | `id` | - |
| 9 | `shelter_facilities` | Amenities provided per shelter (Water, Meds, Power, Food) | `id` | `shelter_id` $\rightarrow$ `shelters(id)` |
| 10 | `resources` | Relief inventory items, units, minimum safe thresholds | `id` | - |
| 11 | `disaster_reports` | Formal SITREP incident reports, casualties, missing persons | `id` | `generated_by` $\rightarrow$ `users(id)` |
| 12 | `notifications` | In-app user notifications and dispatch alerts | `id` | `user_id` $\rightarrow$ `users(id)` |

---

## 4. User Roles and Default Accounts

Passwords are encrypted using Werkzeug's secure PBKDF2/scrypt password hashing algorithm:

| Role | Username | Password | Intended Capabilities |
|------|----------|----------|-----------------------|
| **Administrator** | `admin` | `admin123` | Full system control, issue/deactivate alerts, verify incidents, assign rescue teams, close tickets, register shelters, manage resource inventory, export CSV reports. |
| **Emergency Responder** | `responder1` | `resp123` | View assigned & pending incidents, update status to *Rescued*, exchange field messages with victims, toggle team operational readiness. |
| **Citizen** | `citizen1` | `citizen123` | Trigger instant GPS SOS beacon, submit detailed reports with photos, track personal request progress, find nearest shelters, receive area disaster alerts. |

---

## 5. RESTful API Endpoint Documentation

All endpoints return uniform JSON payloads with standard HTTP status codes (`200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`):

```json
{
  "success": true,
  "message": "Operation completed successfully.",
  "data": { ... }
}
```

### Authentication & Sessions (`/api/auth`)
- `POST /api/register` – Register a citizen or responder account.
- `POST /api/login` – Authenticate user and initialize secure session cookie.
- `POST /api/logout` – Destroy session.
- `GET /api/session` – Query active session profile details.
- `PUT /api/profile` – Update telephone, locality, or GPS coordinates.
- `GET /api/notifications` – Retrieve unread in-app dispatch notifications.
- `PUT /api/notifications/<id>/read` – Mark notification as read.

### Module 1: Alerts & Weather (`/api/alerts`)
- `GET /api/alerts` – List alerts (filters: `severity`, `type`, `locality`, `active`).
- `GET /api/alerts/<id>` – Retrieve single alert details.
- `POST /api/alerts` – *(Admin only)* Issue new disaster alert.
- `PUT /api/alerts/<id>` – *(Admin only)* Modify alert description/severity.
- `DELETE /api/alerts/<id>` – *(Admin only)* Deactivate / soft-delete alert.
- `GET /api/weather` – Proxy endpoint for live weather telemetry.
- `GET /api/alerts/check-thresholds` – Fetch automated rule definitions.
- `GET /api/alerts/stats` – Aggregate alert counts by severity & hazard category.

### Module 2: Emergencies & Rescue (`/api/requests`)
- `GET /api/requests` – Query incident board (role-restricted: citizen sees own, responder sees assigned, admin sees all).
- `GET /api/requests/<id>` – Detailed incident view with timeline history and assigned units.
- `POST /api/requests` – File emergency report (supports JSON and `multipart/form-data` image upload).
- `PUT /api/requests/<id>/status` – Advance state workflow (`Verified`, `Rescued`, `Closed`).
- `POST /api/requests/<id>/assign` – *(Admin only)* Assign response team and auto-dispatch.
- `GET /api/requests/<id>/messages` – Retrieve field message thread (supports `?after=timestamp` for polling).
- `POST /api/requests/<id>/messages` – Post new message to incident channel.
- `GET /api/requests/stats` – Metrics on SOS count, pending, and resolved incidents.

### Module 3: Shelters, Resources & Reports (`/api/shelters`, `/api/resources`, `/api/reports`)
- `GET /api/shelters` – Fetch shelters with optional `lat` and `lon` to calculate nearest distance.
- `GET /api/shelters/<id>` – Single shelter profile and facilities list.
- `POST /api/shelters` – *(Admin only)* Register new relief camp.
- `PUT /api/shelters/<id>` – *(Admin only)* Update capacity and occupancy.
- `GET /api/resources` – List supply stockpile (filters: `category`, `low_stock=true`).
- `POST /api/resources` – *(Admin only)* Add new resource item to ledger.
- `PUT /api/resources/<id>` – *(Admin only)* Modify inventory threshold and location.
- `PUT /api/resources/<id>/restock` – *(Admin only)* Replenish inventory quantity.
- `DELETE /api/resources/<id>` – *(Admin only)* Delete item from ledger.
- `GET /api/reports/summary` – Consolidated KPI metrics for operational dashboard.
- `GET /api/reports/csv` – *(Admin only)* Download CSV export (`type=requests|resources|alerts`).

---

## 6. Installation & Execution Guide

### Prerequisites
1. **Python 3.10+**
2. **MySQL 8.0 Server** (Service running on port 3306)

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Verify your `.env` file matches your MySQL password:
```env
FLASK_SECRET_KEY=sentrygrid-csa4310-super-secret-key-2026
FLASK_DEBUG=True
FLASK_PORT=5000

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=NewPassword123
DB_NAME=sentrygrid_db

OPENWEATHER_API_KEY=
```

### Step 3: Initialize Database & Sample Data
Execute the automated database setup script:
```bash
python init_db.py
```
This script:
1. Creates `sentrygrid_db`.
2. Executes `database/schema.sql` to build all 12 normalized tables.
3. Inserts default users (`admin`, `responder1`, `citizen1`) with cryptographically hashed passwords.
4. Executes `database/sample_data.sql` to populate realistic Indian city coordinates, active alerts, incidents, shelters, and resources.

### Step 4: Run the Application
```bash
python app.py
```
Open your browser and navigate to:
**http://localhost:5000**

---

## 7. Running Automated Tests

SentryGrid includes comprehensive test suites covering unit and end-to-end integration flows against live MySQL:

```bash
# Run unit and permission tests
python test_api.py

# Run end-to-end integration test across all 3 modules
python test_all_features.py
```

Expected output:
```
Ran 4 tests in 2.269s
OK
```

---

## 8. Academic Viva Presentation Guide (CSA4310)

When presenting this project to your faculty, highlight how the implementation fulfills core **Internet Programming** principles:

1. **AJAX vs. Page Reloads:**  
   Show how emergency reports, messages, and alerts update asynchronously using `$.ajax()`, preventing disruptive full-page browser refreshes.
2. **Fetch API vs. jQuery AJAX:**  
   Explain that internal application routes use jQuery AJAX for seamless DOM integration, while external third-party telemetry (weather) demonstrates modern JavaScript ES6 `fetch().then()` syntax.
3. **HTTP Verbs:**  
   Point out that the REST APIs strictly use standard HTTP methods:
   - `GET` for idempotent data retrieval (alerts, requests, shelters)
   - `POST` for resource creation (SOS, emergency filing, messages)
   - `PUT` for updates (status workflow advancement, profile updates, restocking)
   - `DELETE` for soft/hard deletion (alert deactivation, resource removal).
4. **Security & Parameterized Queries:**  
   Demonstrate that all database interactions use `%s` parameterized tuples (`cursor.execute(sql, (param,))`), guaranteeing 100% protection against SQL Injection attacks. Mention that passwords use PBKDF2/scrypt one-way cryptographic hashing.
5. **State Progression Workflow:**  
   Walk through the 5-stage emergency pipeline in Module 2: citizen files SOS $\rightarrow$ status is `Reported` $\rightarrow$ admin clicks *Verify Incident* $\rightarrow$ status becomes `Verified` $\rightarrow$ admin assigns unit $\rightarrow$ status becomes `Dispatched` $\rightarrow$ responder extricates victims $\rightarrow$ status becomes `Rescued` $\rightarrow$ admin archives $\rightarrow$ status becomes `Closed`.
6. **Geolocation & Distance Math:**  
   Show that the application uses the browser's `navigator.geolocation` API to capture latitude and longitude, and uses the server-side Haversine spherical trigonometric formula to sort shelters nearest to the user.
