-- Stage 2: Nested Funnel Analysis (View -> Cart -> Purchase)
-- A session is counted as a cart ONLY if it had a view.
-- A session is counted as a purchase ONLY if it had a view AND a cart.

-- 1. Overall Nested Session-Level Funnel
WITH session_flags AS (
    SELECT 
        user_session,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS has_view,
        MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
    FROM events
    WHERE user_session IS NOT NULL
    GROUP BY user_session
)
SELECT 
    COUNT(*) AS total_tracked_sessions,
    SUM(has_view) AS stage1_view_sessions,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1 ELSE 0 END) AS stage2_cart_nested_sessions,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1 ELSE 0 END) AS stage3_purchase_nested_sessions,
    -- Step conversion rates
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / SUM(has_view) * 100, 2) AS view_to_cart_cvr_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / SUM(has_view) * 100), 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) * 100, 2) AS cart_to_purchase_cvr_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) * 100), 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / SUM(has_view) * 100, 2) AS overall_view_to_purchase_cvr_pct
FROM session_flags;

-- 2. Nested Category Funnel
WITH session_cat AS (
    SELECT 
        user_session,
        CASE 
            WHEN category_code IS NULL OR category_code = '' THEN 'Unknown / Uncategorized'
            WHEN INSTR(category_code, '.') > 0 THEN SUBSTR(category_code, 1, INSTR(category_code, '.') - 1)
            ELSE category_code 
        END AS main_category,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS has_view,
        MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
    FROM events
    WHERE user_session IS NOT NULL
    GROUP BY user_session, main_category
)
SELECT 
    main_category,
    SUM(has_view) AS view_sessions,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1 ELSE 0 END) AS cart_sessions_nested,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1 ELSE 0 END) AS purchase_sessions_nested,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100, 2) AS view_to_cart_rate_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100), 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END), 0) * 100, 2) AS cart_to_purchase_rate_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END), 0) * 100), 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100, 2) AS overall_conversion_rate_pct
FROM session_cat
GROUP BY main_category
ORDER BY view_sessions DESC;
