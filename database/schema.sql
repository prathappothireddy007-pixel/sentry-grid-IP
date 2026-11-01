-- ============================================================
-- SentryGrid Database Schema
-- A comprehensive disaster management system database
-- ============================================================

-- Create the database if it doesn't already exist
CREATE DATABASE IF NOT EXISTS sentrygrid_db;

-- Switch to the sentrygrid database
USE sentrygrid_db;

-- ============================================================
-- DROP TABLES in reverse dependency order to avoid FK errors
-- Tables with foreign keys are dropped before the tables they reference
-- ============================================================

DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS disaster_reports;
DROP TABLE IF EXISTS resources;
DROP TABLE IF EXISTS shelter_facilities;
DROP TABLE IF EXISTS shelters;
DROP TABLE IF EXISTS emergency_messages;
DROP TABLE IF EXISTS team_assignments;
DROP TABLE IF EXISTS response_teams;
DROP TABLE IF EXISTS emergency_status_history;
DROP TABLE IF EXISTS emergency_requests;
DROP TABLE IF EXISTS disaster_alerts;
DROP TABLE IF EXISTS users;

-- ============================================================
-- TABLE 1: users
-- Stores all system users: citizens, responders, and admins
-- ============================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique user ID
    username VARCHAR(50) UNIQUE NOT NULL,                       -- Login username (must be unique)
    email VARCHAR(100) UNIQUE NOT NULL,                         -- User email (must be unique)
    password_hash VARCHAR(255) NOT NULL,                        -- Hashed password (never store plaintext!)
    full_name VARCHAR(100) NOT NULL,                            -- Display name
    role ENUM('citizen', 'responder', 'admin') NOT NULL DEFAULT 'citizen',  -- User role for access control
    phone VARCHAR(20),                                          -- Contact phone number
    locality VARCHAR(200),                                      -- User's locality/area
    latitude DECIMAL(10, 8),                                    -- GPS latitude of user's location
    longitude DECIMAL(11, 8),                                   -- GPS longitude of user's location
    is_active BOOLEAN DEFAULT TRUE,                             -- Whether the account is active
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the account was created
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- Last update time
);

-- ============================================================
-- TABLE 2: disaster_alerts
-- Active disaster alerts created by admins or fetched from APIs
-- ============================================================
CREATE TABLE disaster_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique alert ID
    created_by INT NOT NULL,                                    -- Which admin/user created this alert
    disaster_type ENUM('flood', 'cyclone', 'earthquake', 'landslide', 
                       'heatwave', 'tsunami', 'wildfire', 'storm') NOT NULL,  -- Type of disaster
    severity ENUM('Low', 'Medium', 'High', 'Critical') NOT NULL,             -- How severe the disaster is
    title VARCHAR(200) NOT NULL,                                -- Short title for the alert
    description TEXT,                                           -- Detailed description of the disaster
    location VARCHAR(200) NOT NULL,                             -- Human-readable location string
    latitude DECIMAL(10, 8),                                    -- GPS latitude of disaster
    longitude DECIMAL(11, 8),                                   -- GPS longitude of disaster
    safety_instructions TEXT,                                   -- Instructions for citizens
    is_active BOOLEAN DEFAULT TRUE,                             -- Whether this alert is still active
    source VARCHAR(100) DEFAULT 'Manual',                       -- Where this alert came from (Manual, API, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the alert was created
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- Last update time
    -- Foreign key: the user who created this alert must exist
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- ============================================================
-- TABLE 3: emergency_requests
-- SOS and emergency help requests submitted by citizens
-- ============================================================
CREATE TABLE emergency_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique request ID
    user_id INT NOT NULL,                                       -- Which citizen submitted this request
    citizen_name VARCHAR(100) NOT NULL,                         -- Name of the person in need
    contact_number VARCHAR(20) NOT NULL,                        -- Phone number to reach them
    emergency_type ENUM('medical', 'fire', 'flood_rescue', 'trapped', 'other') NOT NULL,  -- Type of emergency
    description TEXT,                                           -- Details about the emergency
    location VARCHAR(200),                                      -- Human-readable location
    latitude DECIMAL(10, 8),                                    -- GPS latitude
    longitude DECIMAL(11, 8),                                   -- GPS longitude
    image_path VARCHAR(500),                                    -- Path to uploaded image (if any)
    status ENUM('Reported', 'Verified', 'Dispatched', 'Rescued', 'Closed') DEFAULT 'Reported',  -- Current status
    priority ENUM('Low', 'Medium', 'High', 'Critical') DEFAULT 'Medium',    -- Priority level
    is_sos BOOLEAN DEFAULT FALSE,                               -- Whether this is an SOS (highest urgency)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the request was filed
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- Last update time
    -- Foreign key: the citizen must exist in users table
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- TABLE 4: emergency_status_history
-- Tracks every status change for an emergency request
-- This creates an audit trail for accountability
-- ============================================================
CREATE TABLE emergency_status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique history entry ID
    request_id INT NOT NULL,                                    -- Which emergency request this refers to
    old_status VARCHAR(20),                                     -- Previous status (NULL for first entry)
    new_status VARCHAR(20) NOT NULL,                            -- New status after the change
    changed_by INT NOT NULL,                                    -- Who made this status change
    notes TEXT,                                                 -- Optional notes about the change
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the change happened
    -- Foreign key: cascade delete if the request is removed
    FOREIGN KEY (request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE,
    -- Foreign key: the person who made the change must exist
    FOREIGN KEY (changed_by) REFERENCES users(id)
);

-- ============================================================
-- TABLE 5: response_teams
-- Disaster response teams that can be dispatched to emergencies
-- ============================================================
CREATE TABLE response_teams (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique team ID
    team_name VARCHAR(100) NOT NULL,                            -- Name of the response team
    team_category ENUM('medical', 'fire', 'flood_rescue', 'search_rescue', 'general') NOT NULL,  -- Team specialization
    team_leader VARCHAR(100),                                   -- Name of the team leader
    member_count INT DEFAULT 0,                                 -- Number of members in the team
    phone VARCHAR(20),                                          -- Team contact number
    status ENUM('available', 'deployed', 'off_duty') DEFAULT 'available',  -- Current team status
    base_location VARCHAR(200),                                 -- Where the team is based
    latitude DECIMAL(10, 8),                                    -- GPS latitude of base
    longitude DECIMAL(11, 8),                                   -- GPS longitude of base
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- Record creation time
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- Last update time
);

-- ============================================================
-- TABLE 6: team_assignments
-- Links response teams to emergency requests they're handling
-- ============================================================
CREATE TABLE team_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique assignment ID
    request_id INT NOT NULL,                                    -- The emergency request being handled
    team_id INT NOT NULL,                                       -- The team assigned to it
    assigned_by INT NOT NULL,                                   -- The admin who made the assignment
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,            -- When the team was assigned
    completed_at TIMESTAMP NULL,                                -- When the assignment was completed (NULL if ongoing)
    notes TEXT,                                                 -- Assignment notes
    -- Foreign key: cascade delete if the request is removed
    FOREIGN KEY (request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE,
    -- Foreign key: the team must exist
    FOREIGN KEY (team_id) REFERENCES response_teams(id),
    -- Foreign key: the admin who assigned must exist
    FOREIGN KEY (assigned_by) REFERENCES users(id)
);

-- ============================================================
-- TABLE 7: emergency_messages
-- Chat/communication messages on an emergency request thread
-- ============================================================
CREATE TABLE emergency_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique message ID
    request_id INT NOT NULL,                                    -- Which emergency request this message belongs to
    sender_id INT NOT NULL,                                     -- Who sent the message
    message TEXT NOT NULL,                                      -- The message content
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the message was sent
    -- Foreign key: cascade delete if the request is removed
    FOREIGN KEY (request_id) REFERENCES emergency_requests(id) ON DELETE CASCADE,
    -- Foreign key: the sender must exist
    FOREIGN KEY (sender_id) REFERENCES users(id)
);

-- ============================================================
-- TABLE 8: shelters
-- Emergency shelters where displaced people can take refuge
-- ============================================================
CREATE TABLE shelters (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique shelter ID
    name VARCHAR(200) NOT NULL,                                 -- Name of the shelter
    address VARCHAR(500) NOT NULL,                              -- Full address
    latitude DECIMAL(10, 8) NOT NULL,                           -- GPS latitude
    longitude DECIMAL(11, 8) NOT NULL,                          -- GPS longitude
    total_capacity INT NOT NULL,                                -- Maximum number of people it can hold
    current_occupancy INT DEFAULT 0,                            -- How many people are currently there
    contact_phone VARCHAR(20),                                  -- Shelter contact phone
    contact_email VARCHAR(100),                                 -- Shelter contact email
    is_active BOOLEAN DEFAULT TRUE,                             -- Whether the shelter is currently operational
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- Record creation time
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- Last update time
);

-- ============================================================
-- TABLE 9: shelter_facilities
-- Facilities available at each shelter (water, medical, power, etc.)
-- ============================================================
CREATE TABLE shelter_facilities (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique facility record ID
    shelter_id INT NOT NULL,                                    -- Which shelter has this facility
    facility_name VARCHAR(100) NOT NULL,                        -- Name of the facility (e.g., "Drinking Water")
    is_available BOOLEAN DEFAULT TRUE,                          -- Whether it's currently available
    -- Foreign key: cascade delete if the shelter is removed
    FOREIGN KEY (shelter_id) REFERENCES shelters(id) ON DELETE CASCADE
);

-- ============================================================
-- TABLE 10: resources
-- Inventory of disaster relief resources (food, medicine, equipment)
-- ============================================================
CREATE TABLE resources (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique resource ID
    name VARCHAR(200) NOT NULL,                                 -- Name of the resource
    category ENUM('shelter', 'medical', 'food_water', 'rescue_equipment') NOT NULL,  -- Resource category
    quantity INT NOT NULL DEFAULT 0,                             -- Current quantity in stock
    unit VARCHAR(50) NOT NULL,                                  -- Unit of measurement (kg, liters, units, etc.)
    min_threshold INT DEFAULT 10,                               -- Minimum stock level before alert
    location VARCHAR(200),                                      -- Where the resource is stored
    last_restocked TIMESTAMP NULL,                              -- When it was last restocked
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- Record creation time
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- Last update time
);

-- ============================================================
-- TABLE 11: disaster_reports
-- Summary reports generated for disaster incidents
-- ============================================================
CREATE TABLE disaster_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique report ID
    title VARCHAR(200) NOT NULL,                                -- Report title
    report_type ENUM('incident', 'resource', 'summary') NOT NULL,  -- Type of report
    disaster_type VARCHAR(50),                                  -- What kind of disaster this is about
    affected_location VARCHAR(200),                             -- Area affected
    total_affected INT DEFAULT 0,                               -- Total people affected
    missing_persons INT DEFAULT 0,                              -- Number of missing persons
    casualties INT DEFAULT 0,                                   -- Number of casualties
    description TEXT,                                           -- Detailed report description
    generated_by INT,                                           -- Which admin generated the report
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the report was created
    -- Foreign key: the admin who generated must exist
    FOREIGN KEY (generated_by) REFERENCES users(id)
);

-- ============================================================
-- TABLE 12: notifications
-- Push notifications sent to users about alerts, updates, etc.
-- ============================================================
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,                          -- Unique notification ID
    user_id INT NOT NULL,                                       -- Which user receives this notification
    title VARCHAR(200) NOT NULL,                                -- Notification title
    message TEXT NOT NULL,                                      -- Notification body text
    type ENUM('alert', 'emergency', 'info', 'success', 'warning') DEFAULT 'info',  -- Notification category
    is_read BOOLEAN DEFAULT FALSE,                              -- Whether the user has read it
    link VARCHAR(500),                                          -- Optional link to navigate to
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,             -- When the notification was sent
    -- Foreign key: cascade delete if the user is removed
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- INDEXES for faster queries on frequently searched columns
-- ============================================================

-- Speed up login and user lookup queries
CREATE INDEX idx_users_email ON users(email);
-- Speed up role-based filtering (e.g., find all responders)
CREATE INDEX idx_users_role ON users(role);
-- Speed up fetching only active disaster alerts
CREATE INDEX idx_alerts_active ON disaster_alerts(is_active);
-- Speed up filtering emergency requests by status
CREATE INDEX idx_requests_status ON emergency_requests(status);
-- Speed up finding all requests by a specific user
CREATE INDEX idx_requests_user ON emergency_requests(user_id);
-- Speed up fetching unread notifications for a user
CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read);
