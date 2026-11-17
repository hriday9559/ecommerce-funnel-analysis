-- Stage 1: Table schema, indexes, and validation queries

-- Create table structure
CREATE TABLE IF NOT EXISTS events (
    event_time TEXT,
    event_type TEXT,
    product_id INTEGER,
    category_id INTEGER,
    category_code TEXT,
    brand TEXT,
    price REAL,
    user_id INTEGER,
    user_session TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(user_session);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time);
CREATE INDEX IF NOT EXISTS idx_events_cat ON events(category_code);
CREATE INDEX IF NOT EXISTS idx_events_session_product ON events(user_session, product_id);
CREATE INDEX IF NOT EXISTS idx_events_brand ON events(brand);
CREATE INDEX IF NOT EXISTS idx_events_product ON events(product_id);

-- Validation Summary Queries
SELECT 
    COUNT(*) AS total_rows,
    MIN(event_time) AS min_date,
    MAX(event_time) AS max_date,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT user_session) AS unique_sessions
FROM events;

-- Event Type Distribution
SELECT 
    event_type,
    COUNT(*) AS event_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM events), 2) AS percentage
FROM events
GROUP BY event_type
ORDER BY event_count DESC;

-- Missing values count
SELECT 
    SUM(CASE WHEN category_code IS NULL THEN 1 ELSE 0 END) AS null_category_code,
    SUM(CASE WHEN brand IS NULL THEN 1 ELSE 0 END) AS null_brand,
    SUM(CASE WHEN user_session IS NULL THEN 1 ELSE 0 END) AS null_user_session
FROM events;
