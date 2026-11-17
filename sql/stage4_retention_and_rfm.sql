-- Stage 4: Retention (Calendar-Day Return Rates with Full Window Capping) and RFM Customer Segmentation
-- Retention rule: Only count as 'returned' if the event is on a different calendar day: date(event_time) > date of first event.
-- Observation Window Capping Rule: Max dataset event_time is 2021-02-28.
-- To avoid cohort truncation bias, only users who joined at least 7 days (first_date <= '2021-02-21')
-- or 30 days (first_date <= '2021-01-29') before dataset close are included in 7d and 30d cohorts respectively.

-- 1. All Site Visitors Calendar-Day Return Rate (Capped Windows)
WITH first_visit AS (
    SELECT 
        user_id,
        MIN(date(event_time)) AS first_date
    FROM events
    GROUP BY user_id
),
subsequent_visits AS (
    SELECT 
        e.user_id,
        (julianday(date(e.event_time)) - julianday(f.first_date)) AS day_diff
    FROM events e
    JOIN first_visit f ON e.user_id = f.user_id
    WHERE date(e.event_time) > f.first_date
)
SELECT 
    COUNT(DISTINCT f.user_id) AS total_all_visitors,
    COUNT(DISTINCT CASE WHEN f.first_date <= '2021-02-21' THEN f.user_id END) AS eligible_7d,
    COUNT(DISTINCT CASE WHEN s.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN s.user_id END) AS returned_within_7d,
    ROUND(COUNT(DISTINCT CASE WHEN s.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN s.user_id END) * 100.0 / 
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-02-21' THEN f.user_id END), 2) AS return_rate_7d_pct,
    COUNT(DISTINCT CASE WHEN f.first_date <= '2021-01-29' THEN f.user_id END) AS eligible_30d,
    COUNT(DISTINCT CASE WHEN s.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN s.user_id END) AS returned_within_30d,
    ROUND(COUNT(DISTINCT CASE WHEN s.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN s.user_id END) * 100.0 / 
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-01-29' THEN f.user_id END), 2) AS return_rate_30d_pct
FROM first_visit f
LEFT JOIN subsequent_visits s ON f.user_id = s.user_id;

-- 2. Paying Customers Calendar-Day Return & Repeat Purchase Rates (Capped Windows)
WITH first_purchase AS (
    SELECT 
        user_id,
        MIN(date(event_time)) AS first_date
    FROM events
    WHERE event_type = 'purchase'
    GROUP BY user_id
),
subsequent_site_visits AS (
    SELECT 
        e.user_id,
        (julianday(date(e.event_time)) - julianday(f.first_date)) AS day_diff
    FROM events e
    JOIN first_purchase f ON e.user_id = f.user_id
    WHERE date(e.event_time) > f.first_date
),
subsequent_purchases AS (
    SELECT 
        e.user_id,
        (julianday(date(e.event_time)) - julianday(f.first_date)) AS day_diff
    FROM events e
    JOIN first_purchase f ON e.user_id = f.user_id
    WHERE e.event_type = 'purchase' AND date(e.event_time) > f.first_date
)
SELECT 
    COUNT(DISTINCT f.user_id) AS total_paying_customers,
    COUNT(DISTINCT CASE WHEN f.first_date <= '2021-02-21' THEN f.user_id END) AS eligible_7d,
    COUNT(DISTINCT CASE WHEN f.first_date <= '2021-01-29' THEN f.user_id END) AS eligible_30d,
    -- Site visits on a different calendar day
    COUNT(DISTINCT CASE WHEN sv.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN sv.user_id END) AS site_returned_7d,
    ROUND(COUNT(DISTINCT CASE WHEN sv.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN sv.user_id END) * 100.0 /
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-02-21' THEN f.user_id END), 2) AS site_return_7d_pct,
    COUNT(DISTINCT CASE WHEN sv.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN sv.user_id END) AS site_returned_30d,
    ROUND(COUNT(DISTINCT CASE WHEN sv.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN sv.user_id END) * 100.0 /
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-01-29' THEN f.user_id END), 2) AS site_return_30d_pct,
    -- Repeat purchases on a different calendar day
    COUNT(DISTINCT CASE WHEN sp.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN sp.user_id END) AS repurchased_7d,
    ROUND(COUNT(DISTINCT CASE WHEN sp.day_diff <= 7 AND f.first_date <= '2021-02-21' THEN sp.user_id END) * 100.0 /
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-02-21' THEN f.user_id END), 2) AS repurchase_7d_pct,
    COUNT(DISTINCT CASE WHEN sp.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN sp.user_id END) AS repurchased_30d,
    ROUND(COUNT(DISTINCT CASE WHEN sp.day_diff <= 30 AND f.first_date <= '2021-01-29' THEN sp.user_id END) * 100.0 /
          COUNT(DISTINCT CASE WHEN f.first_date <= '2021-01-29' THEN f.user_id END), 2) AS repurchase_30d_pct
FROM first_purchase f
LEFT JOIN subsequent_site_visits sv ON f.user_id = sv.user_id
LEFT JOIN subsequent_purchases sp ON f.user_id = sp.user_id;

-- 3. Base RFM Metrics per Customer
SELECT 
    user_id,
    ROUND(julianday('2021-03-01') - julianday(MAX(event_time)), 1) AS recency_days,
    COUNT(DISTINCT user_session) AS frequency_orders,
    COUNT(*) AS frequency_items_purchased,
    ROUND(SUM(price), 2) AS monetary_value,
    ROUND(SUM(price) / COUNT(DISTINCT user_session), 2) AS avg_order_value
FROM events
WHERE event_type = 'purchase'
GROUP BY user_id;

-- 4. Segment Summary from rfm_segments table
SELECT 
    segment,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rfm_segments), 2) AS customer_share_pct,
    ROUND(SUM(monetary_value), 2) AS total_revenue,
    ROUND(SUM(monetary_value) * 100.0 / (SELECT SUM(monetary_value) FROM rfm_segments), 2) AS revenue_share_pct,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency_orders), 2) AS avg_orders,
    ROUND(AVG(monetary_value), 2) AS avg_monetary_spend
FROM rfm_segments
GROUP BY segment
ORDER BY total_revenue DESC;
