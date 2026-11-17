-- Stage 5: A/B Test Campaign Comparison Queries (Clean 29 Matched Days)
-- Note: August 5, 2019 is dropped from BOTH groups so both evaluate the exact same 29 days.
-- Daily level metrics avoid treating clicks as independent persons.

-- 1. Daily Paired Performance across 29 Matched Days
SELECT 
    Date,
    "Spend [USD]_control" AS control_spend,
    "Spend [USD]_test" AS test_spend,
    "# of Website Clicks_control" AS control_clicks,
    "# of Website Clicks_test" AS test_clicks,
    "# of Purchase_control" AS control_items_purchased,
    "# of Purchase_test" AS test_items_purchased,
    ROUND(cvr_control * 100, 2) AS control_daily_cvr_pct,
    ROUND(cvr_test * 100, 2) AS test_daily_cvr_pct,
    ROUND(ctr_control * 100, 2) AS control_daily_ctr_pct,
    ROUND(ctr_test * 100, 2) AS test_daily_ctr_pct,
    ROUND(cpa_control, 2) AS control_cpa,
    ROUND(cpa_test, 2) AS test_cpa
FROM ab_test_daily
WHERE Date != '2019-08-05' AND Date != '5.08.2019'
ORDER BY Date;

-- 2. Aggregate Campaign Totals and Daily Means across 29 Matched Days
SELECT 
    'Control Campaign' AS campaign,
    COUNT(Date) AS matched_days,
    ROUND(SUM("Spend [USD]_control"), 2) AS total_spend,
    ROUND(AVG("Spend [USD]_control"), 2) AS avg_daily_spend,
    SUM("# of Website Clicks_control") AS total_clicks,
    ROUND(AVG("# of Website Clicks_control"), 2) AS avg_daily_clicks,
    SUM("# of Purchase_control") AS total_items_purchased,
    ROUND(AVG("# of Purchase_control"), 2) AS avg_daily_items_purchased,
    ROUND(AVG(cvr_control) * 100, 2) AS avg_daily_cvr_pct,
    ROUND(SUM("Spend [USD]_control") / SUM("# of Purchase_control"), 2) AS overall_cost_per_purchase_usd
FROM ab_test_daily
WHERE Date != '2019-08-05' AND Date != '5.08.2019'
UNION ALL
SELECT 
    'Test Campaign' AS campaign,
    COUNT(Date) AS matched_days,
    ROUND(SUM("Spend [USD]_test"), 2) AS total_spend,
    ROUND(AVG("Spend [USD]_test"), 2) AS avg_daily_spend,
    SUM("# of Website Clicks_test") AS total_clicks,
    ROUND(AVG("# of Website Clicks_test"), 2) AS avg_daily_clicks,
    SUM("# of Purchase_test") AS total_items_purchased,
    ROUND(AVG("# of Purchase_test"), 2) AS avg_daily_items_purchased,
    ROUND(AVG(cvr_test) * 100, 2) AS avg_daily_cvr_pct,
    ROUND(SUM("Spend [USD]_test") / SUM("# of Purchase_test"), 2) AS overall_cost_per_purchase_usd
FROM ab_test_daily
WHERE Date != '2019-08-05' AND Date != '5.08.2019';
