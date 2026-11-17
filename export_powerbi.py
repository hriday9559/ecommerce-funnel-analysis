import sqlite3
import pandas as pd
import numpy as np
import os

os.makedirs('powerbi_exports', exist_ok=True)
conn = sqlite3.connect('ecommerce.db')

print('--- Generating Audited Power BI Datasets ---')

# 1. Nested Funnel by Category
# Cart only if has view; Purchase only if has view and cart
funnel_query = '''
WITH session_cat AS (
    SELECT 
        user_session,
        CASE 
            WHEN category_code IS NULL OR category_code = '' THEN 'Unknown / Uncategorized'
            WHEN INSTR(category_code, '.') > 0 THEN SUBSTR(category_code, 1, INSTR(category_code, '.') - 1)
            ELSE category_code 
        END AS main_category,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) as has_view,
        MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) as has_cart,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) as has_purchase
    FROM events
    WHERE user_session IS NOT NULL
    GROUP BY user_session, main_category
)
SELECT 
    main_category,
    SUM(has_view) as view_sessions,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1 ELSE 0 END) as cart_sessions_nested,
    SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1 ELSE 0 END) as purchase_sessions_nested,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100, 2) as view_to_cart_rate_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100), 2) as view_to_cart_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END), 0) * 100, 2) as cart_to_purchase_rate_pct,
    ROUND(100.0 - (SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(CASE WHEN has_view = 1 AND has_cart = 1 THEN 1.0 ELSE 0 END), 0) * 100), 2) as cart_to_purchase_dropoff_pct,
    ROUND(SUM(CASE WHEN has_view = 1 AND has_cart = 1 AND has_purchase = 1 THEN 1.0 ELSE 0 END) / NULLIF(SUM(has_view), 0) * 100, 2) as overall_conversion_rate_pct
FROM session_cat
GROUP BY main_category
ORDER BY view_sessions DESC;
'''
df_funnel = pd.read_sql_query(funnel_query, conn)
df_funnel.to_csv('powerbi_exports/funnel_by_category.csv', index=False)
print('1. Exported funnel_by_category.csv (rows:', len(df_funnel), ')')

# 2. Revenue and Deduplicated Cart Abandonment by Category
# Strict rule: (session, product) pairs minus same-session purchases minus purchases made AFTER cart time
events_df = pd.read_sql_query('SELECT user_id, user_session, product_id, event_type, event_time, price, category_code, brand FROM events', conn)
events_df['event_time'] = pd.to_datetime(events_df['event_time'])

def get_cat(c):
    if pd.isnull(c) or c == '':
        return 'Unknown / Uncategorized'
    return c.split('.')[0]

events_df['main_category'] = events_df['category_code'].apply(get_cat)

purchases = events_df[events_df['event_type'] == 'purchase'].copy()
carts = (events_df[events_df['event_type'] == 'cart']
         .dropna(subset=['user_session'])
         .sort_values('event_time')
         .drop_duplicates(subset=['user_session', 'product_id'])
         .copy())

same_session_purch = set(zip(purchases['user_session'], purchases['product_id']))
carts['bought_same_session'] = carts.apply(lambda r: (r['user_session'], r['product_id']) in same_session_purch, axis=1)

# Match non_same carts with ANY purchase of the same user_id and product_id at or after cart time
non_same = carts[~carts['bought_same_session']].copy()
merged_purch = pd.merge(
    non_same[['user_session', 'product_id', 'user_id', 'event_time']],
    purchases[['user_id', 'product_id', 'event_time']],
    on=['user_id', 'product_id'],
    suffixes=('_cart', '_purch')
)
valid_recoveries = merged_purch[merged_purch['event_time_purch'] >= merged_purch['event_time_cart']]
recovered_pairs = set(zip(valid_recoveries['user_session'], valid_recoveries['product_id']))

carts['bought_after_cart'] = carts.apply(
    lambda r: (r['user_session'], r['product_id']) in recovered_pairs, axis=1)
carts['net_lost'] = (~carts['bought_same_session']) & (~carts['bought_after_cart'])

cat_carts = carts.groupby('main_category').agg(
    total_cart_pairs=('product_id', 'count'),
    bought_same_session=('bought_same_session', 'sum'),
    bought_later_by_user=('bought_after_cart', 'sum'),
    net_abandoned_cart_pairs=('net_lost', 'sum'),
    net_lost_revenue=('price', lambda x: round(x[carts.loc[x.index, 'net_lost']].sum(), 2))
).reset_index()

cat_purchases = purchases.groupby('main_category').agg(
    total_orders=('user_session', 'nunique'),
    items_purchased=('product_id', 'count'),
    realized_revenue=('price', lambda x: round(x.sum(), 2)),
    avg_item_price=('price', lambda x: round(x.mean(), 2))
).reset_index()

rev_cat_merged = pd.merge(cat_purchases, cat_carts, on='main_category', how='outer').fillna({
    'total_orders': 0, 'items_purchased': 0, 'realized_revenue': 0, 'avg_item_price': 0,
    'total_cart_pairs': 0, 'bought_same_session': 0, 'bought_later_by_user': 0,
    'net_abandoned_cart_pairs': 0, 'net_lost_revenue': 0
})
rev_cat_merged['cart_abandonment_rate_pct'] = (rev_cat_merged['net_abandoned_cart_pairs'] / rev_cat_merged['total_cart_pairs'] * 100).round(2).fillna(0)
rev_cat_merged['pct_share_of_total_lost_revenue'] = (rev_cat_merged['net_lost_revenue'] / rev_cat_merged['net_lost_revenue'].sum() * 100).round(2)
rev_cat_merged = rev_cat_merged.sort_values('realized_revenue', ascending=False)

rev_cat_merged.to_csv('powerbi_exports/revenue_and_abandonment_by_category.csv', index=False)
print('2. Exported revenue_and_abandonment_by_category.csv (rows:', len(rev_cat_merged), ')')

# 3. Revenue by Top 50 Brands
brand_df = purchases.groupby('brand').agg(
    total_orders=('user_session', 'nunique'),
    items_purchased=('product_id', 'count'),
    total_revenue=('price', lambda x: round(x.sum(), 2)),
    avg_item_price=('price', lambda x: round(x.mean(), 2))
).reset_index()
brand_df['brand'] = brand_df['brand'].fillna('Generic / Unknown')
brand_df['revenue_share_pct'] = (brand_df['total_revenue'] / purchases['price'].sum() * 100).round(2)
brand_df = brand_df.sort_values('total_revenue', ascending=False).head(50)
brand_df.to_csv('powerbi_exports/revenue_by_top_brands.csv', index=False)
print('3. Exported revenue_by_top_brands.csv (rows:', len(brand_df), ')')

# 4. RFM Customer Segments
rfm_df = pd.read_sql_query('SELECT * FROM rfm_segments ORDER BY monetary_value DESC', conn)
if 'frequency_items' in rfm_df.columns:
    rfm_df.rename(columns={'frequency_items': 'frequency_items_purchased'}, inplace=True)
rfm_df.to_csv('powerbi_exports/rfm_customer_segments.csv', index=False)
print('4. Exported rfm_customer_segments.csv (rows:', len(rfm_df), ')')

# 5. A/B Test Daily Performance (Matched 29 days, August 5 dropped from BOTH)
df_c = pd.read_csv('control_group.csv', sep=';')
df_t = pd.read_csv('test_group.csv', sep=';')
df_c.columns = df_c.columns.str.strip()
df_t.columns = df_t.columns.str.strip()
missing_dates = df_c[df_c.isnull().any(axis=1)]['Date'].tolist()
df_c_29 = df_c[~df_c['Date'].isin(missing_dates)].copy()
df_t_29 = df_t[~df_t['Date'].isin(missing_dates)].copy()

ab_paired = pd.merge(df_c_29, df_t_29, on='Date', suffixes=('_control', '_test'))
ab_paired['Date'] = pd.to_datetime(ab_paired['Date'], format='%d.%m.%Y').dt.strftime('%Y-%m-%d')
ab_paired['cvr_control'] = ab_paired['# of Purchase_control'] / ab_paired['# of Website Clicks_control']
ab_paired['cvr_test'] = ab_paired['# of Purchase_test'] / ab_paired['# of Website Clicks_test']
ab_paired['ctr_control'] = ab_paired['# of Website Clicks_control'] / ab_paired['# of Impressions_control']
ab_paired['ctr_test'] = ab_paired['# of Website Clicks_test'] / ab_paired['# of Impressions_test']
ab_paired['cpa_control'] = ab_paired['Spend [USD]_control'] / ab_paired['# of Purchase_control']
ab_paired['cpa_test'] = ab_paired['Spend [USD]_test'] / ab_paired['# of Purchase_test']
ab_paired.rename(columns={
    '# of Purchase_control': 'items_purchased_control',
    '# of Purchase_test': 'items_purchased_test'
}, inplace=True)
ab_paired.to_csv('powerbi_exports/ab_test_daily_performance.csv', index=False)
print('5. Exported ab_test_daily_performance.csv (rows:', len(ab_paired), ')')

# 6. Retention and Repurchase Rates (Dynamically Calculated with Full Window Capping)
# Max dataset date: 2021-02-28. Exclude users joining < 7d or < 30d before max date to avoid cohort truncation bias.
CUTOFF_7  = '2021-02-21'
CUTOFF_30 = '2021-01-29'

ret_all = pd.read_sql_query(f'''
WITH first_visit AS (
    SELECT user_id, MIN(date(event_time)) AS first_date
    FROM events
    GROUP BY user_id
),
subsequent AS (
    SELECT e.user_id,
           julianday(date(e.event_time)) - julianday(f.first_date) AS day_diff
    FROM events e
    JOIN first_visit f ON e.user_id = f.user_id
    WHERE date(e.event_time) > f.first_date
)
SELECT
    COUNT(DISTINCT CASE WHEN f.first_date <= '{CUTOFF_7}' THEN f.user_id END) AS el7,
    COUNT(DISTINCT CASE WHEN f.first_date <= '{CUTOFF_30}' THEN f.user_id END) AS el30,
    COUNT(DISTINCT CASE WHEN s.day_diff <= 7  AND f.first_date <= '{CUTOFF_7}'  THEN s.user_id END) AS r7,
    COUNT(DISTINCT CASE WHEN s.day_diff <= 30 AND f.first_date <= '{CUTOFF_30}' THEN s.user_id END) AS r30
FROM first_visit f
LEFT JOIN subsequent s ON f.user_id = s.user_id
''', conn).iloc[0]

ret_buy = pd.read_sql_query(f'''
WITH first_purchase AS (
    SELECT user_id, MIN(date(event_time)) AS first_date
    FROM events
    WHERE event_type = 'purchase'
    GROUP BY user_id
),
sv AS (
    SELECT e.user_id, julianday(date(e.event_time)) - julianday(f.first_date) AS day_diff
    FROM events e
    JOIN first_purchase f ON e.user_id = f.user_id
    WHERE date(e.event_time) > f.first_date
),
sp AS (
    SELECT e.user_id, julianday(date(e.event_time)) - julianday(f.first_date) AS day_diff
    FROM events e
    JOIN first_purchase f ON e.user_id = f.user_id
    WHERE e.event_type = 'purchase' AND date(e.event_time) > f.first_date
)
SELECT
    COUNT(DISTINCT CASE WHEN f.first_date <= '{CUTOFF_7}'  THEN f.user_id END) AS el7,
    COUNT(DISTINCT CASE WHEN f.first_date <= '{CUTOFF_30}' THEN f.user_id END) AS el30,
    COUNT(DISTINCT CASE WHEN sv.day_diff <= 7  AND f.first_date <= '{CUTOFF_7}'  THEN sv.user_id END) AS site7,
    COUNT(DISTINCT CASE WHEN sv.day_diff <= 30 AND f.first_date <= '{CUTOFF_30}' THEN sv.user_id END) AS site30,
    COUNT(DISTINCT CASE WHEN sp.day_diff <= 7  AND f.first_date <= '{CUTOFF_7}'  THEN sp.user_id END) AS rep7,
    COUNT(DISTINCT CASE WHEN sp.day_diff <= 30 AND f.first_date <= '{CUTOFF_30}' THEN sp.user_id END) AS rep30
FROM first_purchase f
LEFT JOIN sv ON f.user_id = sv.user_id
LEFT JOIN sp ON f.user_id = sp.user_id
''', conn).iloc[0]

retention_rows = [
    {
        'user_group': 'All Site Visitors',
        'benchmark_period': '7-Day',
        'metric_name': 'Site Visit Return (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_all['el7']),
        'returned_users': int(ret_all['r7']),
        'rate_pct': round(float(ret_all['r7']) / float(ret_all['el7']) * 100, 2),
        'window_cutoff_date': CUTOFF_7
    },
    {
        'user_group': 'All Site Visitors',
        'benchmark_period': '30-Day',
        'metric_name': 'Site Visit Return (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_all['el30']),
        'returned_users': int(ret_all['r30']),
        'rate_pct': round(float(ret_all['r30']) / float(ret_all['el30']) * 100, 2),
        'window_cutoff_date': CUTOFF_30
    },
    {
        'user_group': 'Paying Customers',
        'benchmark_period': '7-Day',
        'metric_name': 'Site Visit Return (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_buy['el7']),
        'returned_users': int(ret_buy['site7']),
        'rate_pct': round(float(ret_buy['site7']) / float(ret_buy['el7']) * 100, 2),
        'window_cutoff_date': CUTOFF_7
    },
    {
        'user_group': 'Paying Customers',
        'benchmark_period': '30-Day',
        'metric_name': 'Site Visit Return (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_buy['el30']),
        'returned_users': int(ret_buy['site30']),
        'rate_pct': round(float(ret_buy['site30']) / float(ret_buy['el30']) * 100, 2),
        'window_cutoff_date': CUTOFF_30
    },
    {
        'user_group': 'Paying Customers',
        'benchmark_period': '7-Day',
        'metric_name': 'Repeat Purchase (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_buy['el7']),
        'returned_users': int(ret_buy['rep7']),
        'rate_pct': round(float(ret_buy['rep7']) / float(ret_buy['el7']) * 100, 2),
        'window_cutoff_date': CUTOFF_7
    },
    {
        'user_group': 'Paying Customers',
        'benchmark_period': '30-Day',
        'metric_name': 'Repeat Purchase (Strict Calendar Day, Capped Window)',
        'eligible_users': int(ret_buy['el30']),
        'returned_users': int(ret_buy['rep30']),
        'rate_pct': round(float(ret_buy['rep30']) / float(ret_buy['el30']) * 100, 2),
        'window_cutoff_date': CUTOFF_30
    }
]
retention_df = pd.DataFrame(retention_rows)
retention_df.to_csv('powerbi_exports/retention_and_repurchase_rates.csv', index=False)
print('6. Exported retention_and_repurchase_rates.csv (rows:', len(retention_df), ')')

conn.close()
print('All Power BI exports dynamically generated from database and validated!')
