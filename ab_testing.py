"""
ab_testing.py — A/B test statistical analysis.

Unit of analysis: daily campaign performance (29 matched days).
Evaluates 4 core metrics:
  1. Daily Items Purchased (Primary conversion metric)
  2. Daily Conversion Rate (CVR = Purchases / Clicks)
  3. Daily Website Clicks (Traffic volume metric)
  4. Daily Ad Spend (Campaign cost metric)

Tests: Welch's t-test (independent samples, unequal variance) +
       Wilcoxon signed-rank test (non-parametric paired calendar day differences).
Verdicts are computed programmatically from p-values and confidence intervals.
"""
import pandas as pd
import numpy as np
from scipy import stats

ALPHA = 0.05

def compute_metric_stats(name, c_s, t_s, paired_c, paired_t, kind='count'):
    """Compute Welch t-test, Wilcoxon signed-rank, 95% CI, and lift for a daily metric."""
    n_days = len(c_s)
    diff = t_s.mean() - c_s.mean()
    lift = diff / c_s.mean() * 100

    welch = stats.ttest_ind(t_s, c_s, equal_var=False)
    wilcox = stats.wilcoxon(paired_t, paired_c)

    se = np.sqrt(c_s.var() / n_days + t_s.var() / n_days)
    dof = (c_s.var() / n_days + t_s.var() / n_days)**2 / (
        (c_s.var() / n_days)**2 / (n_days - 1) + (t_s.var() / n_days)**2 / (n_days - 1)
    )
    t_crit = stats.t.ppf(0.975, dof)
    ci_lo = diff - t_crit * se
    ci_hi = diff + t_crit * se

    sig_welch = bool(welch.pvalue < ALPHA)
    sig_wilcox = bool(wilcox.pvalue < ALPHA)
    ci_spans_zero = bool(ci_lo < 0 < ci_hi)

    return {
        'name': name,
        'control_mean': c_s.mean(),
        'test_mean': t_s.mean(),
        'control_std': c_s.std(),
        'test_std': t_s.std(),
        'diff': diff,
        'lift_pct': lift,
        'welch_t': welch.statistic,
        'welch_p': welch.pvalue,
        'wilcox_w': wilcox.statistic,
        'wilcox_p': wilcox.pvalue,
        'ci_lo': ci_lo,
        'ci_hi': ci_hi,
        'sig_welch': sig_welch,
        'sig_wilcox': sig_wilcox,
        'ci_spans_zero': ci_spans_zero,
        'kind': kind
    }

def analyze_ab_test():
    # Read files with semicolon delimiter
    df_c = pd.read_csv('control_group.csv', sep=';')
    df_t = pd.read_csv('test_group.csv',    sep=';')

    df_c.columns = df_c.columns.str.strip()
    df_t.columns = df_t.columns.str.strip()

    # Drop missing date (August 5, 2019) from BOTH groups to ensure identical calendar periods
    missing_dates = df_c[df_c.isnull().any(axis=1)]['Date'].tolist()
    df_c = df_c[~df_c['Date'].isin(missing_dates)].copy()
    df_t = df_t[~df_t['Date'].isin(missing_dates)].copy()

    numeric_cols = ['Spend [USD]', '# of Impressions', 'Reach',
                    '# of Website Clicks', '# of Searches',
                    '# of View Content', '# of Add to Cart', '# of Purchase']
    for col in numeric_cols:
        df_c[col] = pd.to_numeric(df_c[col])
        df_t[col] = pd.to_numeric(df_t[col])

    df_c['cvr'] = df_c['# of Purchase'] / df_c['# of Website Clicks']
    df_t['cvr'] = df_t['# of Purchase'] / df_t['# of Website Clicks']

    paired = pd.merge(df_c, df_t, on='Date', suffixes=('_control', '_test'))
    n_days = len(paired)

    print("=" * 72)
    print(f"      A/B TEST STATISTICAL ANALYSIS — MATCHED {n_days} DAYS")
    print("=" * 72)
    print(f"Data Hygiene: Dropped missing date(s) {missing_dates} from BOTH groups.")
    print("Unit of Analysis: Daily campaign performance (avoids treating clicks as independent persons).\n")

    # Analyze all 4 core metrics
    m_purch = compute_metric_stats(
        'Daily Items Purchased',
        df_c['# of Purchase'], df_t['# of Purchase'],
        paired['# of Purchase_control'], paired['# of Purchase_test'],
        kind='count'
    )

    m_cvr = compute_metric_stats(
        'Daily Conversion Rate (CVR)',
        df_c['cvr'], df_t['cvr'],
        paired['cvr_control'], paired['cvr_test'],
        kind='pct'
    )

    m_clicks = compute_metric_stats(
        'Daily Website Clicks',
        df_c['# of Website Clicks'], df_t['# of Website Clicks'],
        paired['# of Website Clicks_control'], paired['# of Website Clicks_test'],
        kind='count'
    )

    m_spend = compute_metric_stats(
        'Daily Ad Spend',
        df_c['Spend [USD]'], df_t['Spend [USD]'],
        paired['Spend [USD]_control'], paired['Spend [USD]_test'],
        kind='currency'
    )

    # ── 1. Primary Metric: Daily Items Purchased ───────────────────────────
    if not m_purch['sig_welch'] and not m_purch['sig_wilcox'] and m_purch['ci_spans_zero']:
        purch_verdict = (f"NON-SIGNIFICANT at α={ALPHA}. "
                         f"Welch p={m_purch['welch_p']:.4f}, Wilcoxon p={m_purch['wilcox_p']:.4f}. "
                         f"95% CI spans zero [{m_purch['ci_lo']:.2f}, {m_purch['ci_hi']:.2f}]. "
                         "Cannot conclude the test affected purchases.")
    elif m_purch['sig_welch'] and m_purch['sig_wilcox']:
        purch_verdict = (f"SIGNIFICANT at α={ALPHA} by BOTH tests. "
                         f"Welch p={m_purch['welch_p']:.4f}, Wilcoxon p={m_purch['wilcox_p']:.4f}. "
                         f"Lift = {m_purch['lift_pct']:.2f}%.")
    else:
        purch_verdict = (f"MIXED: Welch p={m_purch['welch_p']:.4f}, Wilcoxon p={m_purch['wilcox_p']:.4f}. "
                         "Treat with caution.")

    print("--- 1. Primary Metric: Daily Items Purchased ---")
    print(f"Control daily mean: {m_purch['control_mean']:.2f} (std={m_purch['control_std']:.2f})")
    print(f"Test    daily mean: {m_purch['test_mean']:.2f} (std={m_purch['test_std']:.2f})")
    print(f"Difference:         {m_purch['diff']:+.2f} items/day (lift={m_purch['lift_pct']:+.2f}%)")
    print(f"Welch's t-test:     t = {m_purch['welch_t']:.3f}, p-value = {m_purch['welch_p']:.4f}")
    print(f"Welch's 95% CI:     [{m_purch['ci_lo']:.2f}, {m_purch['ci_hi']:.2f}] items/day")
    print(f"Wilcoxon:           W = {m_purch['wilcox_w']:.1f}, p-value = {m_purch['wilcox_p']:.4f}")
    print(f"Verdict:            {purch_verdict}")

    # ── 2. Secondary Metric: Daily CVR ────────────────────────────────────
    if not m_cvr['sig_welch'] and not m_cvr['sig_wilcox'] and m_cvr['ci_spans_zero']:
        cvr_verdict = (f"NON-SIGNIFICANT at α={ALPHA}. "
                       f"Welch p={m_cvr['welch_p']:.4f}, Wilcoxon p={m_cvr['wilcox_p']:.4f}. "
                       "Cannot attribute CVR change to the campaign.")
    else:
        # BUG FIX: Ensure Wilcoxon p-value uses m_cvr['wilcox_p'], not welch_p
        cvr_verdict = (f"Welch p={m_cvr['welch_p']:.4f}, Wilcoxon p={m_cvr['wilcox_p']:.4f}. "
                       f"Lift = {m_cvr['lift_pct']:+.2f}%. Interpret cautiously.")

    print("\n--- 2. Secondary Metric: Daily Conversion Rate (CVR = Purchases/Clicks) ---")
    print(f"Control mean CVR:   {m_cvr['control_mean']*100:.2f}% (std={m_cvr['control_std']:.4f})")
    print(f"Test    mean CVR:   {m_cvr['test_mean']*100:.2f}% (std={m_cvr['test_std']:.4f})")
    print(f"Difference:         {m_cvr['diff']*100:+.2f}% (lift={m_cvr['lift_pct']:+.2f}%)")
    print(f"Welch's t-test:     t = {m_cvr['welch_t']:.3f}, p-value = {m_cvr['welch_p']:.4f}")
    print(f"Welch's 95% CI:     [{m_cvr['ci_lo']*100:+.2f}%, {m_cvr['ci_hi']*100:+.2f}%]")
    print(f"Wilcoxon:           W = {m_cvr['wilcox_w']:.1f}, p-value = {m_cvr['wilcox_p']:.4f}")
    print(f"Verdict:            {cvr_verdict}")

    # ── 3. Traffic Metric: Daily Website Clicks ────────────────────────────
    sig_clicks = "SIGNIFICANT" if (m_clicks['sig_welch'] and m_clicks['sig_wilcox']) else "NON-SIGNIFICANT (p > 0.05)"
    print("\n--- 3. Traffic Metric: Daily Website Clicks ---")
    print(f"Control daily mean: {m_clicks['control_mean']:,.1f} clicks (std={m_clicks['control_std']:.1f})")
    print(f"Test    daily mean: {m_clicks['test_mean']:,.1f} clicks (std={m_clicks['test_std']:.1f})")
    print(f"Difference:         {m_clicks['diff']:+,.1f} clicks/day (lift={m_clicks['lift_pct']:+.2f}%)")
    print(f"Welch's t-test:     t = {m_clicks['welch_t']:.3f}, p-value = {m_clicks['welch_p']:.4f}")
    print(f"Welch's 95% CI:     [{m_clicks['ci_lo']:+,.1f}, {m_clicks['ci_hi']:+,.1f}] clicks/day")
    print(f"Wilcoxon:           W = {m_clicks['wilcox_w']:.1f}, p-value = {m_clicks['wilcox_p']:.4f}")
    print(f"Verdict:            {sig_clicks}")

    # ── 4. Cost Metric: Daily Ad Spend ────────────────────────────────────
    sig_spend = "SIGNIFICANT (Spent more, p < 0.05)" if (m_spend['sig_welch'] and m_spend['sig_wilcox']) else "NON-SIGNIFICANT"
    print("\n--- 4. Cost Metric: Daily Ad Spend ---")
    print(f"Control daily mean: ${m_spend['control_mean']:,.2f} (std=${m_spend['control_std']:.2f})")
    print(f"Test    daily mean: ${m_spend['test_mean']:,.2f} (std=${m_spend['test_std']:.2f})")
    print(f"Difference:         ${m_spend['diff']:+,.2f} / day (lift={m_spend['lift_pct']:+.2f}%)")
    print(f"Welch's t-test:     t = {m_spend['welch_t']:.3f}, p-value = {m_spend['welch_p']:.4f}")
    print(f"Welch's 95% CI:     [${m_spend['ci_lo']:+,.2f}, ${m_spend['ci_hi']:+,.2f}]")
    print(f"Wilcoxon:           W = {m_spend['wilcox_w']:.1f}, p-value = {m_spend['wilcox_p']:.4f}")
    print(f"Verdict:            {sig_spend}")

    # ── 5. Campaign Economics ─────────────────────────────────────────────
    tot_spend_c = df_c['Spend [USD]'].sum()
    tot_spend_t = df_t['Spend [USD]'].sum()
    tot_purch_c = df_c['# of Purchase'].sum()
    tot_purch_t = df_t['# of Purchase'].sum()
    cpa_c = tot_spend_c / tot_purch_c
    cpa_t = tot_spend_t / tot_purch_t

    print("\n--- 5. Campaign Economics (Matched 29 Days) ---")
    print(f"Total Ad Spend:     Control ${tot_spend_c:,.2f} | Test ${tot_spend_t:,.2f}  "
          f"({(tot_spend_t-tot_spend_c)/tot_spend_c:+.2%})")
    print(f"Total Purchases:    Control {tot_purch_c:,.0f}  | Test {tot_purch_t:,.0f}  "
          f"({(tot_purch_t-tot_purch_c)/tot_purch_c:+.2%})")
    print(f"Cost per Purchase:  Control ${cpa_c:.2f} | Test ${cpa_t:.2f}  "
          f"({(cpa_t-cpa_c)/cpa_c:+.2%})")

    # Overall verdict: built per metric from both test outcomes (nothing hardcoded)
    def describe(label, m):
        ps = f"Welch p={m['welch_p']:.4f}, Wilcoxon p={m['wilcox_p']:.4f}"
        if m['sig_welch'] and m['sig_wilcox']:
            direction = 'higher' if m['diff'] > 0 else 'lower'
            return f"{label} significantly {direction} ({ps})"
        if m['sig_welch'] or m['sig_wilcox']:
            return f"{label} mixed, significant on one test only ({ps})"
        return f"{label} not significant ({ps})"

    metric_summary = "; ".join([
        describe('purchases', m_purch),
        describe('CVR', m_cvr),
        describe('clicks', m_clicks),
        describe('spend', m_spend),
    ])
    purch_win = m_purch['sig_welch'] and m_purch['sig_wilcox'] and m_purch['diff'] > 0
    if not purch_win:
        overall = (f"THE TEST CAMPAIGN IS NOT A WIN: {metric_summary}. "
                   f"CPA is ${cpa_t:.2f} (test) vs ${cpa_c:.2f} (control). "
                   "Recommend not scaling the test creative.")
    else:
        overall = f"THE TEST CAMPAIGN IS A WIN at α={ALPHA}: {metric_summary}."

    print("\n" + "=" * 72)
    print("OVERALL VERDICT:", overall)
    print("=" * 72)

    return {
        'items_purchased': m_purch,
        'cvr': m_cvr,
        'clicks': m_clicks,
        'spend': m_spend,
        'cpa_control': cpa_c,
        'cpa_test': cpa_t,
        'tot_spend_c': tot_spend_c,
        'tot_spend_t': tot_spend_t,
        'tot_purch_c': tot_purch_c,
        'tot_purch_t': tot_purch_t,
        'verdict': overall
    }

if __name__ == '__main__':
    analyze_ab_test()
