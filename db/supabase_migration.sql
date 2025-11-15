-- Migration file for Supabase places table
-- Run this in your Supabase SQL editor
-- This script is idempotent - you can run it multiple times safely

-- Drop tables if they exist (WARNING: This will delete all data!)
DROP TABLE IF EXISTS event_participants CASCADE;
DROP TABLE IF EXISTS destinations CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS places CASCADE;

-- Create places table
CREATE TABLE places (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  rating DOUBLE PRECISION,
  place_id TEXT UNIQUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create an index on place_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_places_place_id ON places(place_id);

-- Create an index on location for geospatial queries (if needed)
CREATE INDEX IF NOT EXISTS idx_places_location ON places(latitude, longitude);

-- Users table (for storing Google OAuth user info)
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  google_id TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  name TEXT,
  picture_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on google_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

-- Destinations table for saving user destinations/events
CREATE TABLE destinations (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  place_name TEXT NOT NULL,
  address TEXT,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  place_id TEXT,
  place_type TEXT,
  rating DOUBLE PRECISION,
  scheduled_date DATE NOT NULL,
  scheduled_time TIME, -- Optional: can be NULL for all-day events
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'past', 'cancelled')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Event participants table (for join/interested functionality)
CREATE TABLE event_participants (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT REFERENCES destinations(id) ON DELETE CASCADE,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  participation_type TEXT NOT NULL CHECK (participation_type IN ('joined', 'interested')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(event_id, user_id) -- Prevent duplicate participation
);

-- Create indexes for event_participants
CREATE INDEX IF NOT EXISTS idx_event_participants_event ON event_participants(event_id);
CREATE INDEX IF NOT EXISTS idx_event_participants_user ON event_participants(user_id);

-- Note: Status column is now included in the CREATE TABLE statement above
-- The following block is kept for backward compatibility if running on existing tables
-- but is not needed when dropping and recreating tables

-- Create indexes for destinations
CREATE INDEX IF NOT EXISTS idx_destinations_date ON destinations(scheduled_date DESC, scheduled_time DESC);
CREATE INDEX IF NOT EXISTS idx_destinations_location ON destinations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_destinations_user ON destinations(user_id);

-- Insert test data (optional - comment out if you don't want test data)
-- Test Users
INSERT INTO users (google_id, email, name, picture_url) VALUES
('test_google_id_1', 'testuser1@example.com', 'Test User One', 'https://via.placeholder.com/150'),
('test_google_id_2', 'testuser2@example.com', 'Test User Two', 'https://via.placeholder.com/150'),
('test_google_id_3', 'testuser3@example.com', 'Test User Three', NULL)
ON CONFLICT (google_id) DO NOTHING;

-- Test Places
INSERT INTO places (name, address, latitude, longitude, rating, place_id) VALUES
('Test Coffee Shop', '123 Main St, Test City, TC 12345', 40.7128, -74.0060, 4.5, 'test_place_id_1'),
('Test Restaurant', '456 Oak Ave, Test City, TC 12345', 40.7580, -73.9855, 4.2, 'test_place_id_2'),
('Test Park', '789 Park Blvd, Test City, TC 12345', 40.7829, -73.9654, 4.8, 'test_place_id_3')
ON CONFLICT (place_id) DO NOTHING;

-- Test Destinations (events) - Note: user_id references must match actual user IDs from users table
-- Get user IDs first, then insert destinations
DO $$
DECLARE
    user1_id BIGINT;
    user2_id BIGINT;
BEGIN
    -- Get user IDs
    SELECT id INTO user1_id FROM users WHERE google_id = 'test_google_id_1' LIMIT 1;
    SELECT id INTO user2_id FROM users WHERE google_id = 'test_google_id_2' LIMIT 1;
    
    -- Insert test destinations only if users exist
    IF user1_id IS NOT NULL THEN
        INSERT INTO destinations (user_id, place_name, address, latitude, longitude, place_id, place_type, rating, scheduled_date, scheduled_time, status) VALUES
        (user1_id, 'Test Coffee Shop', '123 Main St, Test City, TC 12345', 40.7128, -74.0060, 'test_place_id_1', 'Cafe', 4.5, CURRENT_DATE + INTERVAL '3 days', '14:00:00', 'active'),
        (user1_id, 'Test Restaurant', '456 Oak Ave, Test City, TC 12345', 40.7580, -73.9855, 'test_place_id_2', 'Restaurant', 4.2, CURRENT_DATE + INTERVAL '7 days', '19:30:00', 'active'),
        (user1_id, 'Test Park', '789 Park Blvd, Test City, TC 12345', 40.7829, -73.9654, 'test_place_id_3', 'Park', 4.8, CURRENT_DATE - INTERVAL '2 days', NULL, 'past')
        ON CONFLICT DO NOTHING;
    END IF;
    
    IF user2_id IS NOT NULL THEN
        INSERT INTO destinations (user_id, place_name, address, latitude, longitude, place_id, place_type, rating, scheduled_date, scheduled_time, status) VALUES
        (user2_id, 'Test Coffee Shop', '123 Main St, Test City, TC 12345', 40.7128, -74.0060, 'test_place_id_1', 'Cafe', 4.5, CURRENT_DATE + INTERVAL '5 days', '10:00:00', 'active')
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Test Event Participants
-- User 2 joins User 1's first event, User 3 is interested in User 1's second event
DO $$
DECLARE
    user1_id BIGINT;
    user2_id BIGINT;
    user3_id BIGINT;
    event1_id BIGINT;
    event2_id BIGINT;
BEGIN
    -- Get user IDs
    SELECT id INTO user1_id FROM users WHERE google_id = 'test_google_id_1' LIMIT 1;
    SELECT id INTO user2_id FROM users WHERE google_id = 'test_google_id_2' LIMIT 1;
    SELECT id INTO user3_id FROM users WHERE google_id = 'test_google_id_3' LIMIT 1;
    
    -- Get event IDs (first two events created by user1)
    SELECT id INTO event1_id FROM destinations WHERE user_id = user1_id ORDER BY created_at LIMIT 1;
    SELECT id INTO event2_id FROM destinations WHERE user_id = user1_id ORDER BY created_at OFFSET 1 LIMIT 1;
    
    -- Insert participants only if all IDs exist
    IF user2_id IS NOT NULL AND event1_id IS NOT NULL THEN
        INSERT INTO event_participants (event_id, user_id, participation_type) VALUES
        (event1_id, user2_id, 'joined')
        ON CONFLICT (event_id, user_id) DO NOTHING;
    END IF;
    
    IF user3_id IS NOT NULL AND event2_id IS NOT NULL THEN
        INSERT INTO event_participants (event_id, user_id, participation_type) VALUES
        (event2_id, user3_id, 'interested')
        ON CONFLICT (event_id, user_id) DO NOTHING;
    END IF;
END $$;

