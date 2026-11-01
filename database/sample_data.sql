-- ===================== SAMPLE DATA =====================
-- Sample data for the SentryGrid disaster management system
-- This file populates the database with realistic test data
-- using Indian cities and locations.
-- ========================================================

-- NOTE: Default users are created via the /api/setup endpoint in the Flask app
-- This ensures passwords are properly hashed by the application
-- Default accounts: admin/admin123, responder1/resp123, citizen1/citizen123

USE sentrygrid_db;

-- --------------------------------------------------------
-- DISASTER ALERTS
-- 5 alerts covering different disaster types and severities
-- created_by = 1 (admin user, created via /api/setup)
-- --------------------------------------------------------

INSERT INTO disaster_alerts (created_by, disaster_type, severity, title, description, location, latitude, longitude, safety_instructions, is_active, source) VALUES

-- Alert 1: Severe flooding in Chennai during monsoon season
(1, 'flood', 'Critical', 'Severe Flooding in Chennai',
 'Heavy monsoon rains have caused severe flooding in low-lying areas of Chennai. Water levels have risen above 3 feet in several residential zones. Multiple roads are submerged and public transport is disrupted.',
 'Chennai, Tamil Nadu', 13.08268400, 80.27071800,
 'Move to higher ground immediately. Do not walk or drive through floodwater. Keep emergency kit ready. Follow official evacuation routes. Boil drinking water before consumption.',
 TRUE, 'IMD Weather API'),

-- Alert 2: Cyclone approaching Mumbai coast
(1, 'cyclone', 'High', 'Cyclone Approaching Mumbai Coast',
 'A deep depression over the Arabian Sea has intensified into a cyclonic storm. Wind speeds of 90-110 km/h expected along the Mumbai coastline within 48 hours. Heavy rainfall warning issued.',
 'Mumbai, Maharashtra', 19.07598400, 72.87765600,
 'Secure loose objects outdoors. Stock up on essentials for 72 hours. Stay away from the coast. Keep windows and doors shut. Charge all electronic devices.',
 TRUE, 'IMD Weather API'),

-- Alert 3: Earthquake tremors felt in Delhi-NCR
(1, 'earthquake', 'Medium', 'Earthquake Tremors in Delhi-NCR',
 'An earthquake of magnitude 4.5 on the Richter scale was recorded with its epicenter near Delhi-NCR region. Tremors were felt across the national capital and surrounding areas. No major damage reported yet.',
 'New Delhi, Delhi', 28.61394700, 77.20902100,
 'Drop, Cover, and Hold On. Stay away from windows and heavy furniture. If indoors, stay indoors. If outdoors, move to an open area. Check for gas leaks after tremors stop.',
 TRUE, 'USGS Earthquake API'),

-- Alert 4: Heatwave across Rajasthan
(1, 'heatwave', 'High', 'Extreme Heatwave in Rajasthan',
 'Temperatures have soared above 47°C in parts of Rajasthan. The India Meteorological Department has issued a red alert for severe heatwave conditions expected to persist for the next 5 days.',
 'Jaipur, Rajasthan', 26.91243300, 75.78727100,
 'Stay indoors during peak hours (11 AM - 4 PM). Drink plenty of water and ORS. Wear light cotton clothing. Avoid strenuous outdoor activity. Check on elderly neighbors.',
 TRUE, 'Manual'),

-- Alert 5: Thunderstorm in Kolkata
(1, 'storm', 'Low', 'Thunderstorm Warning for Kolkata',
 'A nor-wester thunderstorm system is expected to hit Kolkata and surrounding districts this evening. Moderate to heavy rainfall with gusty winds up to 60 km/h predicted for 2-3 hours.',
 'Kolkata, West Bengal', 22.57264900, 88.36389500,
 'Stay indoors during the storm. Unplug sensitive electronic equipment. Avoid using landline phones during lightning. Keep a torch handy in case of power cuts.',
 TRUE, 'IMD Weather API');


-- --------------------------------------------------------
-- EMERGENCY REQUESTS
-- 4 requests from citizen (user_id = 3) with various types/statuses
-- --------------------------------------------------------

INSERT INTO emergency_requests (user_id, citizen_name, contact_number, emergency_type, description, location, latitude, longitude, status, priority, is_sos) VALUES

-- Request 1: Medical emergency in Chennai flood zone (Dispatched, Critical)
(3, 'Rajesh Kumar', '9876543210', 'medical',
 'Elderly person with heart condition stranded on the first floor due to flooding. Needs immediate medical evacuation. Water level rising rapidly. Medicines running out.',
 'T. Nagar, Chennai', 13.04091900, 80.23426900,
 'Dispatched', 'Critical', TRUE),

-- Request 2: Family trapped in building (Verified, High)
(3, 'Priya Sharma', '9123456789', 'trapped',
 'A family of 5 including 2 children is trapped on the rooftop of a 2-story building. Water has entered the ground floor. Need rescue boats urgently.',
 'Velachery, Chennai', 12.97566900, 80.21820900,
 'Verified', 'High', FALSE),

-- Request 3: Fire in residential area (Reported, Medium)
(3, 'Amit Patel', '8765432109', 'fire',
 'A fire has broken out in a kitchen on the 3rd floor of an apartment building. Smoke spreading to adjacent floors. Fire extinguisher used but fire is not contained.',
 'Andheri West, Mumbai', 19.13610300, 72.82713600,
 'Reported', 'Medium', FALSE),

-- Request 4: Flood rescue completed (Rescued, High)
(3, 'Sunita Devi', '7654321098', 'flood_rescue',
 'Group of 10 people stranded in a flooded community hall. Water level at waist height. Includes 3 senior citizens and 1 pregnant woman.',
 'Adyar, Chennai', 13.00630600, 80.25726400,
 'Rescued', 'High', TRUE);


-- --------------------------------------------------------
-- EMERGENCY STATUS HISTORY
-- Audit trail showing how each request's status changed over time
-- changed_by = 1 (admin) or 2 (responder)
-- --------------------------------------------------------

INSERT INTO emergency_status_history (request_id, old_status, new_status, changed_by, notes) VALUES

-- Request 1 status progression: Reported → Verified → Dispatched
(1, NULL, 'Reported', 1, 'Emergency request received via SOS button.'),
(1, 'Reported', 'Verified', 1, 'Location confirmed via GPS. Medical team alerted.'),
(1, 'Verified', 'Dispatched', 2, 'Medical Response Unit Alpha dispatched to T. Nagar area.'),

-- Request 2 status progression: Reported → Verified
(2, NULL, 'Reported', 1, 'Emergency request received.'),
(2, 'Reported', 'Verified', 1, 'Verified via phone call. Family confirmed on rooftop.'),

-- Request 3: Just reported, no changes yet
(3, NULL, 'Reported', 1, 'Fire emergency reported. Awaiting verification.'),

-- Request 4 status progression: Reported → Verified → Dispatched → Rescued
(4, NULL, 'Reported', 1, 'SOS flood rescue request received.'),
(4, 'Reported', 'Verified', 1, 'Confirmed by local authorities. Rescue team notified.'),
(4, 'Verified', 'Dispatched', 2, 'Flood Rescue Team deployed with rescue boats.'),
(4, 'Dispatched', 'Rescued', 2, 'All 10 persons rescued successfully and moved to shelter.');


-- --------------------------------------------------------
-- RESPONSE TEAMS
-- 3 specialized disaster response teams
-- --------------------------------------------------------

INSERT INTO response_teams (team_name, team_category, team_leader, member_count, phone, status, base_location, latitude, longitude) VALUES

-- Team 1: Medical team based in Chennai
('Medical Response Unit Alpha', 'medical', 'Dr. Arun Krishnan', 8, '044-25361234',
 'deployed', 'Government General Hospital, Chennai', 13.07868400, 80.27509400),

-- Team 2: Fire rescue team based in Mumbai
('Fire & Rescue Squad Bravo', 'fire', 'Capt. Vikram Singh', 12, '022-23087600',
 'available', 'Mumbai Fire Brigade HQ, Mumbai', 18.93886500, 72.83537500),

-- Team 3: Flood rescue team based in Chennai
('Flood Rescue Team Charlie', 'flood_rescue', 'Lt. Cmdr. Deepa Nair', 10, '044-25394567',
 'available', 'NDRF Base Camp, Alandur, Chennai', 13.00238700, 80.20604200);


-- --------------------------------------------------------
-- TEAM ASSIGNMENTS
-- Links a response team to an emergency request
-- assigned_by = 1 (admin)
-- --------------------------------------------------------

INSERT INTO team_assignments (request_id, team_id, assigned_by, notes) VALUES

-- Medical team assigned to the critical medical emergency (Request 1)
(1, 1, 1, 'Medical Response Unit Alpha dispatched for elderly patient evacuation. ETA 20 minutes.');


-- --------------------------------------------------------
-- EMERGENCY MESSAGES
-- Communication thread on emergency request #1
-- --------------------------------------------------------

INSERT INTO emergency_messages (request_id, sender_id, message) VALUES

-- Conversation on Request 1 between citizen, admin, and responder
(1, 3, 'Please hurry! The water level is rising fast. My grandfather needs his heart medication urgently. We are on the first floor balcony.'),
(1, 1, 'We have dispatched the Medical Response Unit Alpha to your location. They are carrying essential cardiac medications. Please stay calm and keep your phone charged.'),
(1, 2, 'Team en route. ETA 15 minutes. We have a rescue boat and paramedic onboard. Please wave a white cloth from the balcony so we can spot you easily.');


-- --------------------------------------------------------
-- SHELTERS
-- 4 emergency shelters in major Indian cities
-- --------------------------------------------------------

INSERT INTO shelters (name, address, latitude, longitude, total_capacity, current_occupancy, contact_phone, contact_email, is_active) VALUES

-- Shelter 1: School in Chennai converted to relief camp
('Chennai Relief Camp - Anna Nagar',
 'Municipal Higher Secondary School, Anna Nagar West, Chennai - 600040',
 13.08595100, 80.20960600, 500, 320,
 '044-26162000', 'relief.annanagar@tnsdma.gov.in', TRUE),

-- Shelter 2: Community hall in Mumbai
('Mumbai Cyclone Shelter - Worli',
 'BMC Community Hall, Worli Sea Face, Mumbai - 400018',
 19.01452600, 72.81544000, 300, 45,
 '022-24937800', 'shelter.worli@mcgm.gov.in', TRUE),

-- Shelter 3: Sports complex in Delhi
('Delhi Emergency Shelter - Dwarka',
 'Dwarka Sports Complex, Sector 11, Dwarka, New Delhi - 110075',
 28.58153300, 77.04912900, 800, 120,
 '011-25080900', 'shelter.dwarka@ddma.gov.in', TRUE),

-- Shelter 4: Convention center in Kolkata
('Kolkata Flood Relief Centre - Salt Lake',
 'Netaji Indoor Stadium, Salt Lake City, Kolkata - 700098',
 22.57608600, 88.41224800, 600, 210,
 '033-23375200', 'relief.saltlake@wbsdma.gov.in', TRUE);


-- --------------------------------------------------------
-- SHELTER FACILITIES
-- Amenities available at each shelter
-- --------------------------------------------------------

INSERT INTO shelter_facilities (shelter_id, facility_name, is_available) VALUES

-- Facilities at Chennai Relief Camp (Shelter 1)
(1, 'Drinking Water', TRUE),
(1, 'Medical Aid Station', TRUE),
(1, 'Electricity & Lighting', TRUE),
(1, 'Sanitation & Toilets', TRUE),
(1, 'Cooked Food Distribution', TRUE),
(1, 'Baby Care Room', TRUE),

-- Facilities at Mumbai Cyclone Shelter (Shelter 2)
(2, 'Drinking Water', TRUE),
(2, 'Medical Aid Station', TRUE),
(2, 'Electricity & Lighting', TRUE),
(2, 'Sanitation & Toilets', TRUE),
(2, 'Wheelchair Access', TRUE),

-- Facilities at Delhi Emergency Shelter (Shelter 3)
(3, 'Drinking Water', TRUE),
(3, 'Medical Aid Station', TRUE),
(3, 'Electricity & Lighting', TRUE),
(3, 'Sanitation & Toilets', TRUE),
(3, 'Cooked Food Distribution', TRUE),
(3, 'Blankets & Bedding', TRUE),
(3, 'Wi-Fi & Charging Stations', FALSE),  -- Not yet available

-- Facilities at Kolkata Flood Relief Centre (Shelter 4)
(4, 'Drinking Water', TRUE),
(4, 'Medical Aid Station', TRUE),
(4, 'Electricity & Lighting', FALSE),  -- Power outage
(4, 'Sanitation & Toilets', TRUE),
(4, 'Cooked Food Distribution', TRUE);


-- --------------------------------------------------------
-- RESOURCES
-- 8 disaster relief resources across all 4 categories
-- Some are below their minimum threshold to trigger alerts
-- --------------------------------------------------------

INSERT INTO resources (name, category, quantity, unit, min_threshold, location, last_restocked) VALUES

-- Shelter supplies
('Emergency Tents', 'shelter', 45, 'units', 20,
 'Central Warehouse, Chennai', '2024-03-10 08:00:00'),

('Blankets & Sleeping Bags', 'shelter', 8, 'units', 50,
 'Central Warehouse, Chennai', '2024-02-15 10:00:00'),  -- BELOW THRESHOLD

-- Medical supplies
('First Aid Kits', 'medical', 120, 'kits', 30,
 'District Hospital Store, Mumbai', '2024-03-12 14:30:00'),

('Emergency Medicines (Cardiac)', 'medical', 5, 'boxes', 15,
 'Government General Hospital, Chennai', '2024-01-20 09:00:00'),  -- BELOW THRESHOLD

-- Food and water supplies
('Drinking Water Bottles (1L)', 'food_water', 2500, 'bottles', 500,
 'NDRF Supply Depot, Delhi', '2024-03-14 06:00:00'),

('Ready-to-Eat Meal Packs', 'food_water', 3, 'cartons', 10,
 'Relief Supply Center, Kolkata', '2024-02-28 12:00:00'),  -- BELOW THRESHOLD

-- Rescue equipment
('Inflatable Rescue Boats', 'rescue_equipment', 12, 'units', 5,
 'NDRF Base Camp, Chennai', '2024-03-01 07:00:00'),

('Life Jackets', 'rescue_equipment', 7, 'units', 25,
 'Coast Guard Station, Mumbai', '2024-02-10 11:00:00');  -- BELOW THRESHOLD


-- --------------------------------------------------------
-- DISASTER REPORTS
-- 2 summary reports for tracking disaster impact
-- generated_by = 1 (admin)
-- --------------------------------------------------------

INSERT INTO disaster_reports (title, report_type, disaster_type, affected_location, total_affected, missing_persons, casualties, description, generated_by) VALUES

-- Report 1: Chennai flood incident report
('Chennai Monsoon Floods - Situation Report #3',
 'incident', 'flood', 'Chennai, Tamil Nadu',
 15000, 23, 2,
 'Heavy monsoon rains have caused widespread flooding across Chennai. Over 15,000 people have been displaced from low-lying areas including T. Nagar, Velachery, and Adyar. 23 persons are still missing and search operations are ongoing. 2 casualties reported due to drowning. 4 relief camps are operational with a combined capacity of 2,200. NDRF and state disaster response teams are conducting rescue operations round the clock.',
 1),

-- Report 2: Resource status summary
('Weekly Resource Inventory Summary',
 'resource', NULL, 'All Locations',
 0, 0, 0,
 'Weekly summary of disaster relief resource inventory. Critical shortages identified in: Blankets & Sleeping Bags (8/50 units), Emergency Cardiac Medicines (5/15 boxes), Ready-to-Eat Meal Packs (3/10 cartons), and Life Jackets (7/25 units). Immediate restocking required for these items. Procurement orders have been raised with the central supply authority.',
 1);


-- --------------------------------------------------------
-- NOTIFICATIONS
-- 3 sample notifications for different users
-- --------------------------------------------------------

INSERT INTO notifications (user_id, title, message, type, is_read, link) VALUES

-- Notification for admin (user 1): New emergency reported
(1, 'New Emergency Request Received',
 'A new fire emergency has been reported in Andheri West, Mumbai by Amit Patel. Priority: Medium. Please review and verify.',
 'emergency', FALSE, '/admin/emergency/3'),

-- Notification for responder (user 2): Team dispatched
(2, 'Team Assignment Update',
 'Medical Response Unit Alpha has been assigned to Emergency Request #1 (Medical evacuation in T. Nagar). Please coordinate with the team leader Dr. Arun Krishnan.',
 'info', TRUE, '/admin/emergency/1'),

-- Notification for citizen (user 3): Alert in their area
(3, 'Disaster Alert: Severe Flooding in Chennai',
 'A Critical flood alert has been issued for Chennai, Tamil Nadu. Please follow safety instructions and move to higher ground if in a low-lying area. Nearest shelter: Chennai Relief Camp - Anna Nagar.',
 'alert', FALSE, '/citizen/alerts');
