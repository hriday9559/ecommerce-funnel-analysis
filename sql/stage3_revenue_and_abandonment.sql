-- Stage 3: Revenue Realization & Deduplicated Lost Cart Revenue Analysis
-- Note: 'items purchased' is the count of purchase events.
-- Distinct sessions represent unique customer orders.

-- 1. Total Revenue, Order Counts, and Item Counts
SELECT 
    COUNT(DISTINCT user_session) AS total_orders,
    COUNT(*) AS total_items_purchased,
    ROUND(SUM(price), 2) AS total_revenue,
    ROUND(SUM(price) / COUNT(DISTINCT user_session), 2) AS avg_order_value_aov,
    ROUND(AVG(price), 2) AS avg_item_price,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT user_session), 2) AS avg_items_per_order
FROM events
WHERE event_type = 'purchase' AND user_session IS NOT NULL;

-- 2. Revenue and Order Breakdown by Category
WITH cat_purchases AS (
    SELECT 
        CASE 
            WHEN category_code IS NULL OR category_code = '' THEN 'Unknown / Uncategorized'
            WHEN INSTR(category_code, '.') > 0 THEN SUBSTR(category_code, 1, INSTR(category_code, '.') - 1)
            ELSE category_code 
        END AS main_category,
        user_session,
        price
    FROM events
    WHERE event_type = 'purchase' AND user_session IS NOT NULL
)
SELECT 
    main_category,
    COUNT(DISTINCT user_session) AS total_orders,
    COUNT(*) AS items_purchased,
    ROUND(SUM(price), 2) AS realized_revenue,
    ROUND(SUM(price) / COUNT(DISTINCT user_session), 2) AS avg_order_value,
    ROUND(AVG(price), 2) AS avg_item_price,
    ROUND(SUM(price) * 100.0 / (SELECT SUM(price) FROM events WHERE event_type = 'purchase'), 2) AS revenue_share_pct
FROM cat_purchases
GROUP BY main_category
ORDER BY realized_revenue DESC;

-- 3. Top Brands by Revenue
SELECT 
    COALESCE(brand, 'Generic / Unknown') AS brand,
    COUNT(DISTINCT user_session) AS total_orders,
    COUNT(*) AS items_purchased,
    ROUND(SUM(price), 2) AS total_revenue,
    ROUND(AVG(price), 2) AS avg_item_price,
    ROUND(SUM(price) * 100.0 / (SELECT SUM(price) FROM events WHERE event_type = 'purchase'), 2) AS revenue_share_pct
FROM events
WHERE event_type = 'purchase'
GROUP BY brand
ORDER BY total_revenue DESC
LIMIT 15;

-- 4. Deduplicated Cart Loss with User Subsequent Repurchase Deduction
-- Step A: Unique (session, product) pairs
-- Step B: Deduct products bought in the same session
-- Step C: Deduct pairs recovered later: the same user bought the same product
--         at ANY time >= the cart time (not just the user's first purchase).
--         Pairs whose only purchases came before the cart stay lost.
WITH distinct_carts AS (
    SELECT 
        user_session,
        product_id,
        user_id,
        MIN(event_time) AS cart_time,
        price,
        CASE 
            WHEN category_code IS NULL OR category_code = '' THEN 'Unknown / Uncategorized'
            WHEN INSTR(category_code, '.') > 0 THEN SUBSTR(category_code, 1, INSTR(category_code, '.') - 1)
            ELSE category_code 
        END AS main_category,
        COALESCE(brand, 'Generic / Unknown') AS brand
    FROM events
    WHERE event_type = 'cart' AND user_session IS NOT NULL
    GROUP BY user_session, product_id
),
same_session_purchases AS (
    SELECT DISTINCT user_session, product_id
    FROM events
    WHERE event_type = 'purchase' AND user_session IS NOT NULL
),
classified AS (
    SELECT
        c.*,
        CASE WHEN s.product_id IS NOT NULL THEN 1 ELSE 0 END AS in_session,
        CASE WHEN s.product_id IS NULL AND EXISTS (
            SELECT 1 FROM events p
            WHERE p.event_type = 'purchase'
              AND p.user_id = c.user_id
              AND p.product_id = c.product_id
              AND p.event_time >= c.cart_time
        ) THEN 1 ELSE 0 END AS recovered
    FROM distinct_carts c
    LEFT JOIN same_session_purchases s
        ON c.user_session = s.user_session AND c.product_id = s.product_id
)
SELECT 
    main_category,
    COUNT(*) AS total_cart_pairs,
    SUM(in_session) AS bought_in_session,
    SUM(recovered) AS bought_later_by_user,
    SUM(CASE WHEN in_session = 0 AND recovered = 0 THEN 1 ELSE 0 END) AS net_abandoned_cart_pairs,
    ROUND(SUM(CASE WHEN in_session = 0 AND recovered = 0 THEN price ELSE 0 END), 2) AS net_lost_revenue,
    ROUND(SUM(CASE WHEN in_session = 0 AND recovered = 0 THEN price ELSE 0 END) * 100.0 /
          SUM(SUM(CASE WHEN in_session = 0 AND recovered = 0 THEN price ELSE 0 END)) OVER (), 2) AS pct_share_of_total_lost_revenue
FROM classified
GROUP BY main_category
ORDER BY net_lost_revenue DESC;
