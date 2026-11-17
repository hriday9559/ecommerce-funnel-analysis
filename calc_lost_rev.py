"""
calc_lost_rev.py — Cart abandonment and lost revenue analysis.

RULE (applied consistently with SQL stage3):
  A session-abandoned cart pair is "recovered" if the SAME user later
  purchased the SAME product at ANY time >= the cart event time.
  (Checking only the first purchase missed repeat buyers who purchased before AND after).
"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('ecommerce.db')
print('Loading events...')
df = pd.read_sql_query(
    'SELECT user_id, user_session, product_id, event_type, event_time, '
    'price, category_code, brand FROM events', conn)
conn.close()

df['event_time'] = pd.to_datetime(df['event_time'])

# ── 1. Distinct (user_session, product_id) cart pairs ──────────────────────
carts = (df[df['event_type'] == 'cart']
         .dropna(subset=['user_session'])
         .sort_values('event_time')
         .drop_duplicates(subset=['user_session', 'product_id'])
         .copy())

total_pairs = len(carts)
print(f'Total distinct (session, product) cart pairs: {total_pairs:,}')

# ── 2. Flag: bought in the SAME session ────────────────────────────────────
purchases = df[df['event_type'] == 'purchase'].copy()
same_sess = set(zip(purchases['user_session'], purchases['product_id']))
carts['bought_same_session'] = carts.apply(
    lambda r: (r['user_session'], r['product_id']) in same_sess, axis=1)

# ── 3. Recoveries: ANY purchase by same user of same product >= cart time ──
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

# Net lost = abandoned in session AND no purchase at or after cart time
carts['net_lost'] = (~carts['bought_same_session']) & (~carts['bought_after_cart'])

assert carts['bought_same_session'].sum() + carts['bought_after_cart'].sum() + carts['net_lost'].sum() == total_pairs, \
    "Mutually exclusive parts sum check failed!"

print('\n--- BREAKDOWN OF DEDUPLICATED CARTS ---')
n_same = carts['bought_same_session'].sum()
n_after = carts['bought_after_cart'].sum()
n_lost = carts['net_lost'].sum()

print(f"  Bought in same session:             {n_same:,}  (${carts[carts['bought_same_session']]['price'].sum():,.2f})")
print(f"  Recovered later (ANY purchase >= cart time): {n_after:,}  (${carts[carts['bought_after_cart']]['price'].sum():,.2f})")
print(f"  Net truly lost cart pairs:          {n_lost:,}  (${carts[carts['net_lost']]['price'].sum():,.2f})")
print(f"  Parts sum check: {n_same:,} + {n_after:,} + {n_lost:,} == {total_pairs:,}")

# ── 4. Category breakdown ──────────────────────────────────────────────────
def get_cat(c):
    if pd.isnull(c) or c == '':
        return 'Unknown / Uncategorized'
    return c.split('.')[0]

carts['main_category'] = carts['category_code'].apply(get_cat)
net_lost_df = carts[carts['net_lost']].copy()
total_lost_rev = net_lost_df['price'].sum()

cat_loss = (net_lost_df.groupby('main_category')['price']
            .agg(net_abandoned_pairs='count', net_lost_revenue='sum')
            .reset_index())
cat_loss['pct_of_total_lost'] = (cat_loss['net_lost_revenue'] / total_lost_rev * 100).round(2)
cat_loss = cat_loss.sort_values('net_lost_revenue', ascending=False)

print('\n--- Lost Revenue by Category ---')
print(cat_loss.to_string(index=False))

comp_row = cat_loss[cat_loss['main_category'] == 'computers']
if not comp_row.empty:
    comp_pct = comp_row['pct_of_total_lost'].values[0]
    print(f"\nComputers share of lost revenue: {comp_pct}% (${comp_row['net_lost_revenue'].values[0]:,.2f} / ${total_lost_rev:,.2f})")

# ── 5. Brand breakdown ─────────────────────────────────────────────────────
net_lost_df['brand_clean'] = net_lost_df['brand'].fillna('Generic / Unknown')
brand_loss = (net_lost_df.groupby('brand_clean')['price']
              .agg(abandoned_pairs='count', lost_revenue='sum')
              .reset_index())
brand_loss['pct_of_total_lost'] = (brand_loss['lost_revenue'] / total_lost_rev * 100).round(2)
brand_loss = brand_loss.sort_values('lost_revenue', ascending=False)

print('\n--- Lost Revenue by Top 10 Brands ---')
print(brand_loss.head(10).to_string(index=False))
