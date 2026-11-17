# E-Commerce Funnel, Retention & A/B Test Analysis

**Tools:** Python (Pandas, SciPy), SQL (SQLite), Power BI

## Business Problem
An online electronics store wanted to know where it loses customers and revenue, who its best customers are, and whether a new ad campaign was worth the extra spend. I analyzed 884K clickstream events (Sep 2020 - Feb 2021) and a 29-day A/B campaign test to answer this.

## Key Findings
- **Funnel:** 91.55% of browsing sessions never reach the cart. Of sessions that reach the cart, 50.31% complete a purchase (4.25% overall).
- **Revenue:** $5.13M across 24,344 orders (AOV $210.53). Computers drive 72.76% of revenue.
- **Cart abandonment:** $4.23M in net lost cart revenue, with 78.41% in computer hardware.
- **Retention:** only 7.47% of buyers place a repeat order on a later day within 30 days.
- **Customers:** 2,368 "At Risk" buyers generated 23.99% of revenue but haven't purchased in about 110 days.
- **A/B test:** the Test campaign spent 11.64% more (p = 0.006) with no significant change in purchases (p = 0.847). Not a win.

## Dashboard
![Funnel page](images/dashboard_funnel.png)
![Customer segments page](images/dashboard_segments.png)
![A/B test page](images/dashboard_ab.png)

## Data Sources
- Events: [dataset name and link], [license]
- A/B test: [dataset name and link], [license]

## Project Structure & Architecture

```
├── README.md                                  <- Executive report, audited findings, and strategic recommendations
├── events.csv                                 <- Raw clickstream event data (885,129 records; not in git)
├── control_group.csv                          <- Daily performance for Control campaign (August 2019)
├── test_group.csv                             <- Daily performance for Test campaign (August 2019)
├── ecommerce.db                               <- Indexed SQLite analytical database (built by clean_and_load.py; not in git)
├── computed_facts.json                        <- Key computed figures referenced in this report
├── requirements.txt                           <- Python dependencies
├── clean_and_load.py                          <- Data ingestion and database creation script
├── ab_testing.py                              <- Welch's t-test and Wilcoxon daily A/B testing script (computed verdicts)
├── calc_lost_rev.py                           <- Strict after-cart-time cart loss calculation script
├── export_powerbi.py                          <- Automated Power BI CSV export pipeline (dynamically computed)
├── skeptical_audit.py                         <- Programmatic validation audit with strict assertions
├── sql/                                       <- Modular, stage-specific SQL queries
│   ├── stage1_schema_and_checks.sql           <- Schema definition, 8 indexes, and validation queries
│   ├── stage2_funnel_analysis.sql             <- Nested session and category funnel SQL
│   ├── stage3_revenue_and_abandonment.sql     <- Orders, revenue, and unified cart loss SQL
│   ├── stage4_retention_and_rfm.sql           <- Window-capped calendar-day retention and RFM customer segmentation SQL
│   └── stage5_ab_test_queries.sql             <- Matched 29-day daily A/B campaign queries
└── powerbi_exports/                           <- Clean analytical CSVs exported directly from analytical models
    ├── funnel_by_category.csv                 <- Nested funnel conversions and drop-offs by category (15 rows)
    ├── revenue_and_abandonment_by_category.csv<- Realized orders, revenue, and net lost cart revenue (15 rows)
    ├── revenue_by_top_brands.csv              <- Top 50 revenue-generating brands
    ├── rfm_customer_segments.csv              <- 21,304 paying customer scores and segments
    ├── ab_test_daily_performance.csv          <- Clean 29-day daily campaign metrics (matched dates)
    └── retention_and_repurchase_rates.csv     <- Dynamically computed window-capped retention and repurchase rates (6 rows)
```

---

## How to Run

`events.csv` and `ecommerce.db` are not stored in git (see `.gitignore`) because they are large. To rebuild everything:

1. Place the raw clickstream file `events.csv` (885,129 rows, 9 columns) in the project root.
2. Install dependencies: `pip install -r requirements.txt`
3. Build the database (drops 655 exact duplicates, creates the 8 indexes): `python clean_and_load.py`
4. Regenerate the Power BI exports: `python export_powerbi.py`
5. Run the analyses: `python calc_lost_rev.py` and `python ab_testing.py`
6. Verify every figure in this README: `python skeptical_audit.py` (all 7 checks should pass)

## Detailed Findings by Stage

### Stage 1: Data Hygiene, Deduplication & Database Setup
* **Raw Dataset:** 885,129 rows across 9 columns (`event_time`, `event_type`, `product_id`, `category_id`, `category_code`, `brand`, `price`, `user_id`, `user_session`).
* **Date Range:** September 24, 2020 11:57:06 UTC to February 28, 2021 23:59:09 UTC (~5 months).
* **Duplicates Dropped:** 655 exact duplicate records (recorded simultaneously for the same user, session, product, and event type).
* **Missing Values:**
  * `category_code`: 236,047 missing (26.69%) — unclassified products.
  * `brand`: 212,232 missing (24.00%) — generic/unbranded products.
  * `user_session`: 162 missing (0.02%) — tracking dropouts.
  * `event_time`, `event_type`, `product_id`, `category_id`, `price`, `user_id`: 100% complete (0 nulls).
* **Cleaned Database:** 884,474 rows loaded into SQLite database `ecommerce.db` in table `events`.
* **Database Indexes:** 8 indexes are created to optimize analytical queries:
  1. `idx_events_user_id` on `user_id`
  2. `idx_events_session` on `user_session`
  3. `idx_events_type` on `event_type`
  4. `idx_events_time` on `event_time`
  5. `idx_events_cat` on `category_code`
  6. `idx_events_session_product` on `(user_session, product_id)`
  7. `idx_events_brand` on `brand`
  8. `idx_events_product` on `product_id`

---

### Stage 2: Nested Funnel Analysis & Recalculated Drop-Offs

Under the audited **nested funnel rules**:
* A session is counted as a **Cart** only if it contained a **View** in the same session.
* A session is counted as a **Purchase** only if it contained both a **View** and a **Cart** in the same session.
* Leaks are eliminated by definition: Views >= Carts >= Purchases across every category.

#### 1. Overall Nested Session Funnel
| Funnel Step | Sessions Reaching Step | Conversion from Prior Step | Step Drop-off (%) | % of Total Sessions |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Product View** | **488,360** | 100.0% *(Baseline)* | 0.0% | 100.0% |
| **Stage 2: Add to Cart (Nested)** | **41,256** | **8.45%** | **91.55%** | 8.45% |
| **Stage 3: Purchase (Nested)** | **20,754** | **50.31%** | **49.69%** | **4.25%** |

*Note on Direct / Express Purchases:* An additional 3,590 sessions recorded a purchase without a preceding in-session cart event (e.g., 1-click checkout or express re-orders). Strictly evaluating the nested browsing path reveals that **50.31%** (20,754 / 41,256) of sessions that view and cart an item proceed to purchase.

#### 2. Nested Funnel Performance by Main Category (Direct from CSV)
| Category | View Sessions | Cart Sessions (Nested) | Purchase Sessions (Nested) | View → Cart (%) | View → Cart Drop-off | Cart → Purchase (%) | Overall Conversion (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Unknown / Uncategorized** | 149,524 | 8,783 | 4,463 | **5.87%** | 94.13% | **50.81%** | **2.98%** |
| **computers** | 148,481 | 19,582 | 9,409 | **13.19%** | 86.81% | **48.05%** | **6.34%** |
| **electronics** | 103,281 | 7,611 | 3,952 | **7.37%** | 92.63% | **51.92%** | **3.83%** |
| **stationery** | 26,926 | 2,489 | 1,466 | **9.24%** | 90.76% | **58.90%** | **5.44%** |
| **appliances** | 25,303 | 1,010 | 530 | **3.99%** | 96.01% | **52.48%** | **2.09%** |
| **auto** | 19,698 | 1,257 | 630 | **6.38%** | 93.62% | **50.12%** | **3.20%** |
| **construction** | 17,602 | 1,154 | 558 | **6.56%** | 93.44% | **48.35%** | **3.17%** |
| **furniture** | 2,146 | 139 | 63 | **6.48%** | 93.52% | **45.32%** | **2.94%** |
| **country_yard** | 1,831 | 39 | 16 | **2.13%** | 97.87% | **41.03%** | **0.87%** |
| **accessories** | 1,308 | 58 | 32 | **4.43%** | 95.57% | **55.17%** | **2.45%** |
| **medicine** | 451 | 18 | 9 | **3.99%** | 96.01% | **50.00%** | **2.00%** |
| **kids** | 282 | 10 | 5 | **3.55%** | 96.45% | **50.00%** | **1.77%** |
| **jewelry** | 187 | 10 | 4 | **5.35%** | 94.65% | **40.00%** | **2.14%** |
| **sport** | 129 | 12 | 2 | **9.30%** | 90.70% | **16.67%** | **1.55%** |
| **apparel** | 87 | 1 | 0 | **1.15%** | 98.85% | **0.00%** | **0.00%** |

*Note on Multi-Category Sessions:* Individual category view sessions sum to more than 488,360 because a single user session can browse products across multiple categories. Each category row represents sessions active within that category.

---

### Stage 3: Revenue Realization & Unified Net Cart Abandonment

#### 1. Realized Revenue & Order Volume
* **Total Store Realized Revenue:** **$5,125,113.92**
* **Total Unique Orders (Distinct User Sessions):** **24,344 orders** (across all categories, 24,849 category-order instances).
* **Total Items Purchased:** **37,343 items**
* **Average Order Value (AOV):** **$210.53 per order** ($5,125,113.92 / 24,344 orders).
* **Average Item Price:** **$137.24 per item** ($5,125,113.92 / 37,343 items).
* **Average Items per Order:** **1.53 items / order**

#### 2. Category Realized Revenue
* **Computers:** **$3,728,835.55** (**72.76%** of store revenue across 10,964 category orders and 16,870 items purchased).
  * Video cards alone accounted for **$2,604,764.80** (50.82% of all revenue).
* **Unknown / Uncategorized:** **$493,896.91** (9.64% across 5,284 orders).
* **Electronics:** **$450,348.57** (8.79% across 4,679 orders).
* **Top 5 Revenue Brands:** MSI ($643,492), Gigabyte ($556,183), Palit ($484,211), ASUS ($330,147), Sapphire ($306,193).

#### 3. Strict Net Lost Cart Revenue Method
To measure lost cart revenue without double-counting:
1. **Deduplication:** Each `(user_session, product_id)` pair is counted exactly once: **49,000 distinct cart line items** representing **$7,881,400.30** in gross carted merchandise.
2. **In-Session Purchases:** **22,987 pairs ($3,287,131.16)** were purchased in the same session.
3. **Session-Abandoned Pairs:** **26,013 pairs ($4,594,269.14)**.
4. **Subsequent Customer Repurchases (Deducted):** **2,349 pairs ($361,401.32)** were purchased by the same user (`user_id` and `product_id` match) **at or after the cart event time**, legitimately recovering the abandoned item. A pair counts as recovered if *any* of that user's purchases of the product came at or after the cart time, so repeat buyers who bought both before and after the cart are recovered.
5. **Purchases Only Before the Cart (NOT Deducted):** **306 pairs ($52,038.66)** where the user's *only* purchases of the product came *before* this cart event stay classified as abandoned, because a past purchase does not recover a future cart.
6. **Net Truly Lost Cart Items:** **23,664 cart line items** resulting in **$4,232,867.82 in net lost revenue**.
   *Verification Check:* 22,987 (same session) + 2,349 (recovered after cart) + 23,664 (net lost) = **49,000 total pairs**.

#### 4. Verification of Category Cart Abandonment & Lost Revenue (Direct from CSV)
Applying this exact method across all 15 categories produces:

| Category | Orders | Items Purchased | Realized Revenue ($) | Total Cart Pairs | Bought in Same Session | Bought Later by User | Net Abandoned Items | Net Lost Revenue ($) | Share of Total Lost Revenue |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **computers** | 10,964 | 16,870 | $3,728,835.55 | 24,608 | 10,663 | 1,208 | **12,737** | **$3,318,999.10** | **78.41%** |
| **Unknown / Uncategorized** | 5,284 | 7,566 | $493,896.91 | 9,416 | 4,643 | 429 | **4,344** | **$331,150.42** | **7.82%** |
| **electronics** | 4,679 | 6,768 | $450,348.57 | 8,171 | 4,107 | 381 | **3,683** | **$330,729.96** | **7.81%** |
| **auto** | 738 | 1,091 | $117,312.54 | 1,309 | 636 | 54 | **619** | **$67,484.36** | **1.59%** |
| **stationery** | 1,748 | 2,919 | $109,670.38 | 2,913 | 1,692 | 160 | **1,061** | **$45,746.44** | **1.08%** |
| **construction** | 655 | 999 | $108,682.40 | 1,224 | 577 | 55 | **592** | **$61,437.76** | **1.45%** |
| **appliances** | 617 | 904 | $105,299.99 | 1,058 | 536 | 43 | **479** | **$61,800.44** | **1.46%** |
| **country_yard** | 18 | 23 | $4,339.47 | 40 | 16 | 1 | **23** | **$8,581.10** | **0.20%** |
| **furniture** | 85 | 115 | $2,090.82 | 147 | 64 | 14 | **69** | **$1,592.85** | **0.04%** |
| **accessories** | 38 | 56 | $2,084.41 | 61 | 32 | 2 | **27** | **$1,134.54** | **0.03%** |
| **sport** | 3 | 6 | $1,706.40 | 12 | 2 | 2 | **8** | **$2,367.66** | **0.06%** |
| **medicine** | 10 | 11 | $454.00 | 18 | 9 | 0 | **9** | **$336.83** | **0.01%** |
| **kids** | 5 | 10 | $322.38 | 11 | 6 | 0 | **5** | **$1,416.00** | **0.03%** |
| **jewelry** | 5 | 5 | $70.10 | 11 | 4 | 0 | **7** | **$78.30** | **0.00%** |
| **apparel** | 0 | 0 | $0.00 | 1 | 0 | 0 | **1** | **$12.06** | **0.00%** |
| **Total / Storewide** | **24,849** | **37,343** | **$5,125,113.92** | **49,000** | **22,987** | **2,349** | **23,664** | **$4,232,867.82** | **100.0%** |

* **Computers Net Lost Revenue:** **$3,318,999.10**
* **Total Store Net Lost Revenue:** **$4,232,867.82**
* **Computers Share of Total Net Lost Revenue:** **78.41%** ($3,318,999.10 / $4,232,867.82)

---

### Stage 4: Cohort-Capped Calendar-Day Retention & Customer Segmentation

#### 1. Observation Window Capping & Retention Rates
Because the dataset spans September 24, 2020 through February 28, 2021, users who joined during the final 7 or 30 days of February 2021 did not have a full observation window to return. Uncapped denominators artificially dilute retention rates. 

To eliminate cohort truncation bias, we apply strict window capping:
* **7-Day Retention Cohort:** restricted to users whose first event occurred on or before **2021-02-21** (7 days before dataset end).
* **30-Day Retention Cohort:** restricted to users whose first event occurred on or before **2021-01-29** (30 days before dataset end).
* **Calendar-Day Definition:** A return visit or repurchase requires `date(event_time) > date of first event/purchase`.

| User Cohort | Observation Window | Metric | Eligible Cohort Users | Returned Users | Audited Rate (%) | Window Cutoff Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **All Site Visitors** | 7-Day | Site Visit Return (Strict Calendar Day, Capped Window) | 390,930 | 22,684 | **5.80%** | 2021-02-21 |
| **All Site Visitors** | 30-Day | Site Visit Return (Strict Calendar Day, Capped Window) | 331,650 | 25,257 | **7.62%** | 2021-01-29 |
| **Paying Customers** | 7-Day | Site Visit Return (Strict Calendar Day, Capped Window) | 20,345 | 3,872 | **19.03%** | 2021-02-21 |
| **Paying Customers** | 30-Day | Site Visit Return (Strict Calendar Day, Capped Window) | 16,853 | 3,763 | **22.33%** | 2021-01-29 |
| **Paying Customers** | 7-Day | Repeat Purchase (Strict Calendar Day, Capped Window) | 20,345 | 1,191 | **5.85%** | 2021-02-21 |
| **Paying Customers** | 30-Day | Repeat Purchase (Strict Calendar Day, Capped Window) | 16,853 | 1,259 | **7.47%** | 2021-01-29 |

*Critical Retention Insights:*
* Among eligible site visitors, **5.80%** return to the platform on a later calendar day within a week, rising to **7.62%** within a month.
* Among paying customers with a full 30-day window, **22.33%** return to browse the site on a later calendar day, but only **7.47%** place a repeat order. Over **92.5% of paying customers do not place a second order within 30 days**.

#### 2. RFM Customer Segments (21,304 Paying Customers)
Segmented by Recency (days since last purchase relative to March 1, 2021), Frequency (distinct purchasing sessions), and Monetary Value (total spend):

| Customer Segment | Customer Count | % of Customers | Avg. Recency (Days Ago) | Avg. Orders | Avg. Items Purchased | Avg. Spend ($) | Total Revenue ($) | Revenue Share (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Potential Loyalists** | 6,065 | **28.47%** | 34.3 | 1.05 | 1.82 | $362.32 | **$2,197,444.66** | **42.88%** |
| **At Risk (High Value / Inactive)** | 2,368 | **11.12%** | 109.5 | 1.54 | 2.95 | $519.15 | **$1,229,337.21** | **23.99%** |
| **Champions (VIPs)** | 1,141 | **5.36%** | 33.1 | 2.30 | 4.03 | $844.45 | **$963,518.36** | **18.80%** |
| **Needs Attention** | 3,982 | **18.69%** | 93.9 | 1.00 | 1.37 | $77.05 | **$306,830.41** | **5.99%** |
| **Lost / Hibernating** | 4,297 | **20.17%** | 133.7 | 1.00 | 1.36 | $71.07 | **$305,406.02** | **5.96%** |
| **Recent / New Customers** | 3,451 | **16.20%** | 35.7 | 1.00 | 1.00 | $35.52 | **$122,577.26** | **2.39%** |
| **Total / Sum** | **21,304** | **100.00%** | — | — | — | — | **$5,125,113.92** | **100.00%** |

*Verification:* Customer count sums to exactly 21,304 (100.00%) and realized revenue sums to exactly $5,125,113.92 (100.00%).

---

### Stage 5: A/B Marketing Campaign (Daily Analysis & Computed Verdict)

#### 1. Data Cleaning & Methodology
* **Matched Timeframe:** August 5, 2019 had missing metrics in the Control group. It was dropped from **both groups**, ensuring both campaigns are evaluated over the exact same **29 matched calendar days**.
* **Unit of Analysis:** Daily campaign performance ($N = 29$ days). Individual clicks are not treated as independent observations due to intra-day session clustering and campaign-level bid adjustments.
* **Statistical Tests Run:**
  1. **Welch’s Two-Sample t-test** (unequal variance, independent daily samples).
  2. **Wilcoxon Signed-Rank Test** (non-parametric paired test on matched calendar dates).

#### 2. Statistical Test Results across 29 Matched Days
| Metric | Control (29 Days) | Test (29 Days) | Absolute Difference | Relative Lift | Welch’s t-test ($t, p$) | Wilcoxon Test ($W, p$) | Welch’s 95% Confidence Interval | Statistically Significant? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Daily Items Purchased** | **522.79** | **512.72** | -10.07 / day | **-1.93%** | $t = -0.194$, $p = \mathbf{0.8469}$ | $W = 201.0$, $p = \mathbf{0.9637}$ | `[-114.07, +93.94]` | **NO ($p > 0.05$)** |
| **Daily Conversion Rate (CVR)** | **11.48%** | **9.10%** | -2.38% | **-20.73%** | $t = -1.569$, $p = \mathbf{0.1232}$ | $W = 171.0$, $p = 0.3250$ | `[-5.43%, +0.67%]` | **NO ($p > 0.05$)** |
| **Daily Clicks** | 5,320.8 | 6,038.2 | +717.4 / day | +13.48% | $t = 1.563$, $p = 0.1237$ | $W = 146.0$, $p = 0.1260$ | `[-202.2, +1,636.9]` | NO ($p > 0.05$) |
| **Daily Ad Spend** | $2,304.07 | $2,572.24 | +$268.17 / day | +11.64% | $t = 2.857$, $p = 0.0060$ | $W = 114.0$, $p = 0.0243$ | `[+$80.15, +$456.20]` | **YES (Spent more)** |

#### 3. Campaign Economics & Programmatic Verdict
* **Total Ad Spend:** Control = **$66,818.00** vs. Test = **$74,595.00** (+$7,777 / +11.64% more spend).
* **Total Items Purchased:** Control = **15,161** vs. Test = **14,869** (-292 items / -1.93%).
* **Cost per Purchase (CPA):** Control = **$4.41** vs. Test = **$5.02** (+13.83% more expensive).
* **Programmatic Verdict:** **THE TEST CAMPAIGN IS NOT A WIN: purchases not significant, and spend was significantly higher.**
  The lift in purchases is statistically non-significant ($p = 0.8469$ on Welch's t-test, $p = 0.9637$ on Wilcoxon), with the 95% confidence interval spanning widely across zero `[-114.07, +93.94]`. Daily ad spend was significantly higher in the Test group on both tests ($p = 0.0060$ Welch, $p = 0.0243$ Wilcoxon). Clicks were numerically higher but not significant ($p = 0.1237$), and the conversion rate was numerically lower but not significant ($p = 0.1232$), resulting in a higher cost per purchase ($5.02 vs. $4.41$) without delivering incremental sales.

---

## 5 Revised Strategic Recommendations

### 1. Optimize Top View-to-Cart Drop-Off Categories (Appliances & Country Yard)
* **Data:** While computer hardware converts from view to cart at 13.19% (the platform's highest), low-conversion categories exhibit severe friction: **appliances convert at only 3.99% (96.01% drop-off)**, **medicine at 3.99%**, and **country_yard at 2.13% (97.87% drop-off)**. *Small-sample caveat:* medicine has only 18 cart sessions (451 views) and country_yard only 39 (1,831 views), so their rates are noisy; treat them as directional and prioritize appliances, which has far more volume.
* **Action:** Target on-page conversion friction specifically in these underperforming product lines:
  * For appliances and home goods: add room visualizers, clearer dimensional specifications, user installation reviews, and upfront delivery charges on product detail pages.
  * Implement sticky "Save to Wishlist" and price-drop alerts to capture early browsing intent before complete departure.

### 2. Implement Triggered High-Value Cart Abandonment Recovery for Computer Hardware
* **Data:** Net lost cart revenue is **$4,232,867.82**, with **78.41% ($3,318,999.10)** concentrated in the computers category. *(Lost revenue is only broken down by top-level category, not by subcategory.)*
* **Action:** Deploy automated multi-step recovery journeys targeting high-value hardware carts:
  * Automated email and SMS notifications dispatched at 1-hour, 12-hour, and 24-hour intervals highlighting inventory levels.
  * Integrate Buy Now, Pay Later (BNPL) or 0% APR installment financing options on product pages and cart summaries for orders above $250 to overcome price threshold resistance.

### 3. Re-engage the "At-Risk" Customer Segment Before Complete Churn
* **Data:** 2,368 At-Risk customers historically generated **$1.23M in revenue (23.99% of total store revenue)** with an average spend of $519 each, but have not made a purchase in an average of 110 days.
* **Action:** Launch an automated win-back workflow offering personalized VIP hardware upgrade incentives (e.g., $30 credit toward their next component purchase, priority restock notification) to reactivate these high-LTV buyers before their affinity expires.

### 4. Halt Test Ad Creative & Reallocate Budget to Cost-Effective Targeting
* **Data:** The Test campaign yielded **no statistically significant lift in purchases ($p = 0.8469$)**, and its conversion rate trended lower ($p = 0.1232$, non-significant), while driving acquisition costs up from **$4.41 to $5.02 (+13.8%)**.
* **Action:** Terminate the Test ad variant. Reallocate budget to the Control campaign audience structure. If testing new creative in the future, emphasize specific technical specifications and value propositions rather than broad, low-intent promotional hooks. Note that the Test variant's higher click volume was not statistically significant ($p = 0.1237$); the confirmed effect is higher spend ($p = 0.0060$) with no significant change in purchases.

### 5. Build Lifecycle Re-engagement to Address Low 30-Day Repeat Purchase Rates
* **Data:** Under audited window-capped cohorts, only **5.85% of buyers place a repeat order on a later calendar day within 7 days**, and only **7.47% within 30 days**. Over 92.5% of customers place only one order during their initial month.
* **Action:** Shift commercial resources from pure one-off acquisition to post-purchase retention:
  * **Automated Post-Purchase Drip Workflows:** Send targeted driver setup guides, compatibility accessories, and complementary equipment recommendations (e.g., monitors, power supplies, thermal paste) 5 to 10 days after order delivery.
  * **Trade-In & Upgrade Cycles:** Establish a structured PC component trade-in program providing credit toward next-generation hardware to establish long-term customer lock-in.

---

## Power BI Dataset Reference

The exported CSV files in [`powerbi_exports/`](powerbi_exports/) reflect all audited calculations:
1. `funnel_by_category.csv`: Nested view → cart → purchase volumes and step drop-offs across 15 categories.
2. `revenue_and_abandonment_by_category.csv`: Realized revenue, distinct orders, items purchased, and net lost cart revenue across all 15 categories (78.41% hardware share).
3. `revenue_by_top_brands.csv`: Top 50 brand rankings with distinct order counts and items purchased.
4. `rfm_customer_segments.csv`: Customer-level RFM scores and business tier classifications for 21,304 buyers.
5. `ab_test_daily_performance.csv`: Matched 29-day daily A/B test data with August 5 dropped from both groups.
6. `retention_and_repurchase_rates.csv`: Dynamically computed, window-capped calendar-day site returns and repeat purchase rates (6 rows).
