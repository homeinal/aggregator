-- Migration: Create race event and course tables
-- Created: 2025-01-26

-- Create enum for recruitment method
CREATE TYPE recruit_type AS ENUM ('first_come', 'lottery');

-- Create race_event table
CREATE TABLE race_event (
    event_id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    thumbnail_url VARCHAR(500),
    official_site_url VARCHAR(500) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create race_course table
CREATE TABLE race_course (
    course_id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES race_event(event_id) ON DELETE CASCADE,
    title VARCHAR(100) NOT NULL,
    event_date DATE,
    registration_start_at TIMESTAMPTZ,
    registration_end_at TIMESTAMPTZ,
    is_closed BOOLEAN DEFAULT FALSE,
    location VARCHAR(200),
    price INTEGER,
    recruit_method recruit_type,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_race_event_official_url ON race_event(official_site_url);
CREATE INDEX idx_race_course_event_id ON race_course(event_id);
CREATE INDEX idx_race_course_event_date ON race_course(event_date);

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for auto-updating updated_at
CREATE TRIGGER update_race_event_updated_at
    BEFORE UPDATE ON race_event
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_race_course_updated_at
    BEFORE UPDATE ON race_course
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE race_event IS 'Stores marathon race event information';
COMMENT ON TABLE race_course IS 'Stores individual race course details for each event';
COMMENT ON COLUMN race_event.official_site_url IS 'Unique URL to prevent duplicate entries';
COMMENT ON COLUMN race_course.recruit_method IS 'Recruitment type: first_come (선착순) or lottery (추첨)';
