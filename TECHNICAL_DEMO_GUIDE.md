# SENTRYGRID v2.0 — TECHNICAL VIVA DEMONSTRATION GUIDE
## Real-Time Disaster Alert & Emergency Response Web Application
**Course:** CSA4310 – Internet Programming Capstone Project  
**Author:** Student Capstone Project  
**Date:** Academic Year 2026  

---

## 1. EXECUTIVE SUMMARY & ARCHITECTURE

**SentryGrid** is a production-quality, multi-hazard disaster monitoring, emergency reporting, and rescue coordination platform.

### Core Architectural Highlights:
1. **Frontend Architecture:**
   - Responsive HTML5 & CSS3 with custom high-contrast dark dashboard styling.
   - Dynamic client-side asynchronous communication using **jQuery AJAX** and the modern **Fetch API**.
   - Dual-mapping engines powered by **Leaflet.js** and **OpenStreetMap** with custom vector styling and real-time markers.
   - Comprehensive analytical visualizations using **Chart.js 4.4** (4 interactive charts).
   - In-app street-level routing powered by **Project OSRM** with resilient mathematical geodesic fallback.

2. **Backend Architecture:**
   - **Python 3.11+ / Flask** micro-framework organized into 8 modular Blueprints (`auth`, `alerts`, `emergencies`, `shelters`, `teams`, `resources`, `reports`, `missing_persons`).
   - Dual Database Support: **MySQL 8.0** enterprise engine with transparent **SQLite** fallback.
   - Security: PBKDF2/scrypt cryptographic password hashing, parameterized SQL execution preventing SQL injection, session-based authentication with role-based access control (RBAC), and sensitive contact phone number privacy masking.

3. **External Real-Time APIs:**
   - **USGS Real-Time Earthquake Hazards Program GeoJSON Feed** (Live worldwide and regional seismic telemetry).
   - **Open-Meteo & OpenWeatherMap APIs** (Live meteorological observations).
   - **OSRM Public Routing API** (Real street network polyline calculation).

---

## 2. STEP-BY-STEP VIVA DEMONSTRATION WORKFLOW

Follow this script to demonstrate all 3 capstone modules and technical capabilities in 10-15 minutes.

### ACT 1: Administrator Command Center & Disaster Monitoring (Module 1)
1. **Login as Administrator:**
   - URL: `http://localhost:5000/login`
   - Username: `admin` | Password: `admin123`
2. **Review the 10 KPI Command Center Widgets:**
   - Point out the 10 real-time metric cards: *Active Alerts*, *Pending Emergencies*, *Rescued / Resolved*, *Available Teams*, *Relief Shelters*, *Hospital Beds*, *Active Missing Persons*, *Found Persons*, *Supply Depot Items*, and *Deficit Alerts*.
3. **Inspect the 4 Interactive Chart.js Visualizations:**
   - *Disaster Alerts by Severity* (Doughnut)
   - *Incidents by Emergency Hazard* (Doughnut)
   - *7-Day Incident Trend Timeline* (Line chart with spline smoothing)
   - *Shelter Capacity vs Occupancy* (Bar chart)
4. **Demonstrate the Multi-Layer Operational Map:**
   - Show how administrators can toggle individual layers: *Incidents*, *Alert Zones*, *Shelters*, *Hospitals*, and *USGS Earthquakes*.
5. **Navigate to Disaster Alerts Console (`/alerts`):**
   - **Live USGS Earthquake Surveillance:** Show live earthquakes plotted on the Leaflet map with magnitude-proportional circles, event depths, distance to locality, and direct links to the official USGS event page.
   - **Multi-Hazard Rule-Based Engine:** Demonstrate the explainable rule classification that evaluates rainfall, wind velocity, and ambient temperature against thresholds.
   - **Issue an Official Alert:** Click "Issue New Alert", fill in title, severity (`Critical`), category (`flood`), and safety instructions. Verify the alert immediately appears on the public board.

---

### ACT 2: Citizen Emergency Reporting & SOS Dispatch (Module 2)
1. **Open an Incognito Window / Log out and Login as Citizen:**
   - Username: `citizen1` | Password: `citizen123`
2. **Demonstrate One-Touch Emergency SOS:**
   - Click the prominent **"SEND SOS NOW"** button on the dashboard or navbar.
   - Select the incident sector (e.g. *Chennai, Velachery Basin*) or click *Use Current Live GPS*.
   - Select emergency category (e.g., *Flood / Submerged Water Rescue*) and submit.
   - Show the generated tracking number: **`SG-2026-XXXX`** (e.g., `SG-2026-0004`).
3. **File a Detailed Incident Report (`/emergencies`):**
   - Click **"File Emergency Request"**.
   - Input citizen name, telephone, emergency category (*Trapped Persons*), detailed notes, and attach an image file.
   - Submit and verify the incident enters the strictly enforced 5-stage workflow:
     $$\text{Reported} \longrightarrow \text{Verified} \longrightarrow \text{Dispatched} \longrightarrow \text{Rescued} \longrightarrow \text{Closed}$$

---

### ACT 3: Smart Rescue Dispatch & Squad Recommendation (Module 2)
1. **Return to Administrator Console:**
   - Open the new incident console for `SG-2026-XXXX`.
   - Click **"Advance Status to Verified"**.
2. **Trigger the Heuristic Dispatch Recommendation Engine:**
   - Click **"Assign Rescue Response Unit"**.
   - Highlight the **Smart Squad Recommendation Widget**:
     - Evaluates Haversine distance from squad base to incident coordinates.
     - Computes specialization matching (e.g., *Flood Rescue Squad* for submerged rescues).
     - Factors in current active ticket workload.
     - Generates explainable percentage match (e.g., *96% Match: Direct specialization match, 1.8 km away, 0 active backlog*).
   - Select the #1 recommended unit and click **Deploy Unit**.
   - Note the status automatically advances to **Dispatched** and triggers an in-app notification to field responders!

---

### ACT 4: Missing Persons Management with Privacy Protection (Module 3)
1. **Navigate to Missing Persons (`/missing-persons`):**
   - Show the dedicated module with active cases, search filters, and last-seen map markers.
2. **Explain Privacy-by-Design Phone Masking:**
   - As a citizen, show that contact numbers are masked (e.g., `98765****0`) to prevent harassment.
   - As an admin or case creator, show that contact numbers are unmasked for rescue verification.
3. **File a New Missing Person Case:**
   - Click **"File Missing Person Incident Report"**.
   - Input full name, age, last-seen date/location, and contact telephone.
   - Submit and show the unique case number: **`MP-2026-XXXX`**.
4. **Lifecycle Transition:**
   - Admin/Responder can update status to *Search Active* or *Located* with an audit note.

---

### ACT 5: Hospitals Directory & In-App Leaflet Evacuation Routing (Module 3)
1. **Navigate to Shelters & Medical Centers (`/shelters`):**
   - Switch between **Relief Shelters** and **Hospitals** tabs.
   - Show live bed availability meters (*330 / 2230 Available Beds*) and Trauma Level badges.
2. **Execute In-App Evacuation Routing:**
   - Click **"Route to Facility"** on any shelter or hospital card.
   - SentryGrid contacts the **OSRM Public Routing API**, calculating turn-by-turn geometry.
   - Watch the glowing cyan route polyline draw on the Leaflet map with distance in km, transit duration in minutes, and an official **Disaster Safety Advisory**.

---

### ACT 6: Relief Logistics & Immutable Movement Audit Trail (Module 3)
1. **Navigate to Resource Inventory (`/resources`):**
   - Point out categorized supplies (Medical, Shelter, Food/Water, Rescue Gear).
   - Show low-stock threshold deficit badges (*LOW DEFICIT* vs *OPTIMAL*).
2. **Allocate Supplies to Field:**
   - Click **"Allocate"** on Emergency Tents.
   - Specify quantity, target facility (*Relief Shelter*), and operational notes.
   - Show that allocating more than available stock is strictly prevented (no negative inventory).
3. **Verify the Stock Movement & Dispatch Audit Ledger:**
   - Scroll down to the immutable ledger: shows the timestamp, item name, movement type badge, quantity, destination, and admin username who authorized it.

---

## 3. SUMMARY OF CODE QUALITY & VERIFICATION

| Verification Metric | Value |
|---------------------|-------|
| Automated Test Suites | `test_all_features.py`, `test_api.py`, `test_enhanced_features.py` |
| Total Automated Tests | **19 Tests** |
| Test Pass Rate | **100% (19 Passed, 0 Failed)** |
| Database Schema | 15 Relational Tables with Indexes and Foreign Keys |
| Flask Blueprints | 8 Modular Blueprints |
| External Live APIs | USGS GeoJSON Feed, Open-Meteo, OSRM Public Routing |
| Frontend Components | Leaflet.js (2 map consoles), Chart.js (4 charts), Custom Modals |

---

## 4. FREQUENTLY ASKED VIVA QUESTIONS (AND STRONG TECHNICAL ANSWERS)

**Q1: How does SentryGrid prevent race conditions and negative inventory balances?**  
*Answer:* In `routes/resources.py`, the `allocate_resource` endpoint queries the current stock within a transactional boundary, asserts `current_stock >= requested_quantity`, and rolls back the transaction if the check fails before updating and inserting into `resource_movements`.

**Q2: Why use Leaflet.js with OSRM instead of Google Maps API?**  
*Answer:* Leaflet.js with OpenStreetMap and Project OSRM is fully open-source, requires zero proprietary API keys or paid quotas, and guarantees offline fallback capabilities via server-side Haversine geodesic vectors if the external routing engine becomes unavailable during a disaster.

**Q3: How is citizen privacy safeguarded in the Missing Persons module?**  
*Answer:* In `routes/missing_persons.py`, the query checks `session.get('role')`. If the user is an ordinary citizen and not the case owner, the contact telephone number is dynamically masked using regex before JSON serialization (`98765****0`). Admins and responders receive the unmasked contact.

**Q4: How does the Smart Dispatch Recommendation Engine work?**  
*Answer:* In `routes/emergencies.py`, `recommend_teams()` runs a multi-factor scoring algorithm: +30 points for matching squad specialization (e.g., flood rescue squad for flood emergencies), up to +20 points for close Haversine proximity, +15 points for zero active incident backlog, and penalties for squads with 2+ active deployments.
