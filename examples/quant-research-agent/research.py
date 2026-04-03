"""Quantitative Research: Magnificent 7 Comprehensive Analysis.

This script conducts a full quant research analysis using synthetic market data
calibrated from real historical parameters. It demonstrates the analysis pipeline
that the agent would run using its tools.

Sections:
1. Individual Risk-Return Profiles
2. Correlation Structure & Diversification
3. Equal-Weight Portfolio Backtest vs SPY
4. Factor Exposure Analysis
5. VaR/CVaR Risk Assessment
6. Investment Conclusions
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

from synthetic_data import generate_price_data, ASSET_PARAMS

# ============================================================================
# Configuration
# ============================================================================

MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
FACTORS = ["SPY", "IWM", "IWD", "IWF", "MTUM", "QUAL"]
BENCHMARK = "SPY"
ALL_TICKERS = MAG7 + [t for t in FACTORS if t not in MAG7]
N_DAYS = 756  # 3 years

print("=" * 80)
print("QUANTITATIVE RESEARCH REPORT")
print("Magnificent 7 Tech Stocks: Comprehensive Analysis")
print(f"Analysis Period: ~3 years ({N_DAYS} trading days)")
print("Data: Synthetic (calibrated from historical parameters)")
print("=" * 80)

# ============================================================================
# 1. Generate Data
# ============================================================================

prices = generate_price_data(ALL_TICKERS, n_days=N_DAYS, seed=42)
returns = prices.pct_change().dropna()

print(f"\nData generated: {len(prices)} days, {prices.index[0].date()} to {prices.index[-1].date()}")

# ============================================================================
# 2. Individual Risk-Return Profiles
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 1: INDIVIDUAL RISK-RETURN PROFILES")
print("=" * 80)

profiles = []
for ticker in MAG7:
    r = returns[ticker]
    close = prices[ticker]

    ann_ret = r.mean() * 252
    ann_vol = r.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    max_dd = (close / close.cummax() - 1).min()
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0
    total_ret = close.iloc[-1] / close.iloc[0] - 1

    profiles.append({
        "Ticker": ticker,
        "Total Return (%)": round(total_ret * 100, 1),
        "Ann. Return (%)": round(ann_ret * 100, 1),
        "Ann. Volatility (%)": round(ann_vol * 100, 1),
        "Sharpe Ratio": round(sharpe, 2),
        "Max Drawdown (%)": round(max_dd * 100, 1),
        "Calmar Ratio": round(calmar, 2),
        "Skewness": round(float(r.skew()), 2),
        "Kurtosis": round(float(r.kurtosis()), 2),
    })

df_profiles = pd.DataFrame(profiles)
print("\n" + df_profiles.to_string(index=False))

# Rankings
print("\n--- Rankings ---")
sorted_sharpe = sorted(profiles, key=lambda x: x["Sharpe Ratio"], reverse=True)
print(f"Best Sharpe:      {sorted_sharpe[0]['Ticker']} ({sorted_sharpe[0]['Sharpe Ratio']})")
print(f"Worst Sharpe:     {sorted_sharpe[-1]['Ticker']} ({sorted_sharpe[-1]['Sharpe Ratio']})")
sorted_vol = sorted(profiles, key=lambda x: x["Ann. Volatility (%)"])
print(f"Lowest Vol:       {sorted_vol[0]['Ticker']} ({sorted_vol[0]['Ann. Volatility (%)']}%)")
print(f"Highest Vol:      {sorted_vol[-1]['Ticker']} ({sorted_vol[-1]['Ann. Volatility (%)']}%)")
sorted_dd = sorted(profiles, key=lambda x: x["Max Drawdown (%)"])
print(f"Deepest Drawdown: {sorted_dd[0]['Ticker']} ({sorted_dd[0]['Max Drawdown (%)']}%)")

# ============================================================================
# 3. Correlation Structure
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 2: CORRELATION STRUCTURE & DIVERSIFICATION")
print("=" * 80)

corr = returns[MAG7].corr()
print("\nPearson Correlation Matrix:")
print(corr.round(3).to_string())

# Average pairwise correlation
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
avg_corr = corr.values[mask].mean()
print(f"\nAverage pairwise correlation: {avg_corr:.3f}")

# Identify strongest and weakest pairs
pairs = []
for i in range(len(MAG7)):
    for j in range(i + 1, len(MAG7)):
        pairs.append((MAG7[i], MAG7[j], corr.iloc[i, j]))

pairs.sort(key=lambda x: abs(x[2]), reverse=True)
print("\nMost correlated pairs:")
for a, b, c in pairs[:3]:
    print(f"  {a}-{b}: {c:.3f}")
print("\nLeast correlated pairs:")
for a, b, c in sorted(pairs, key=lambda x: abs(x[2]))[:3]:
    print(f"  {a}-{b}: {c:.3f}")

# Eigenvalue analysis for diversification
eigenvalues = np.linalg.eigvalsh(corr)
eigenvalues = sorted(eigenvalues, reverse=True)
total_var = sum(eigenvalues)
pct_first = eigenvalues[0] / total_var * 100
print(f"\nPCA Concentration:")
print(f"  1st eigenvalue explains: {pct_first:.1f}% of variance")
print(f"  Top 3 eigenvalues explain: {sum(eigenvalues[:3]) / total_var * 100:.1f}% of variance")
if pct_first > 60:
    print("  WARNING: High concentration — these stocks move together significantly")

# ============================================================================
# 4. Equal-Weight Portfolio Backtest
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 3: EQUAL-WEIGHT PORTFOLIO BACKTEST vs SPY")
print("=" * 80)

weights = {t: 1.0 / len(MAG7) for t in MAG7}
port_returns = sum(returns[t] * w for t, w in weights.items())
bench_returns = returns[BENCHMARK]

port_cum = (1 + port_returns).cumprod()
bench_cum = (1 + bench_returns).cumprod()

# Portfolio metrics
p_ann_ret = port_returns.mean() * 252
p_ann_vol = port_returns.std() * np.sqrt(252)
p_sharpe = p_ann_ret / p_ann_vol
p_max_dd = (port_cum / port_cum.cummax() - 1).min()

# Benchmark metrics
b_ann_ret = bench_returns.mean() * 252
b_ann_vol = bench_returns.std() * np.sqrt(252)
b_sharpe = b_ann_ret / b_ann_vol
b_max_dd = (bench_cum / bench_cum.cummax() - 1).min()

# Relative metrics
active_returns = port_returns - bench_returns
tracking_error = active_returns.std() * np.sqrt(252)
info_ratio = active_returns.mean() * 252 / tracking_error if tracking_error > 0 else 0

cov = np.cov(port_returns, bench_returns)
beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0
alpha = p_ann_ret - beta * b_ann_ret
correlation = np.corrcoef(port_returns, bench_returns)[0, 1]

print(f"\n{'Metric':<30} {'Portfolio':>12} {'SPY':>12} {'Difference':>12}")
print("-" * 66)
print(f"{'Total Return (%)':<30} {(port_cum.iloc[-1] - 1) * 100:>11.1f}% {(bench_cum.iloc[-1] - 1) * 100:>11.1f}% {((port_cum.iloc[-1] - bench_cum.iloc[-1])) * 100:>11.1f}%")
print(f"{'Annualized Return (%)':<30} {p_ann_ret * 100:>11.1f}% {b_ann_ret * 100:>11.1f}% {(p_ann_ret - b_ann_ret) * 100:>11.1f}%")
print(f"{'Annualized Volatility (%)':<30} {p_ann_vol * 100:>11.1f}% {b_ann_vol * 100:>11.1f}% {(p_ann_vol - b_ann_vol) * 100:>11.1f}%")
print(f"{'Sharpe Ratio':<30} {p_sharpe:>12.3f} {b_sharpe:>12.3f} {p_sharpe - b_sharpe:>12.3f}")
print(f"{'Max Drawdown (%)':<30} {p_max_dd * 100:>11.1f}% {b_max_dd * 100:>11.1f}% {(p_max_dd - b_max_dd) * 100:>11.1f}%")
print(f"\n{'Relative Metrics':<30}")
print("-" * 42)
print(f"{'Beta to SPY':<30} {beta:>12.3f}")
print(f"{'Alpha (annualized %)':<30} {alpha * 100:>11.2f}%")
print(f"{'Tracking Error (%)':<30} {tracking_error * 100:>11.2f}%")
print(f"{'Information Ratio':<30} {info_ratio:>12.3f}")
print(f"{'Correlation to SPY':<30} {correlation:>12.4f}")

# Monthly returns
monthly_port = port_returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
monthly_bench = bench_returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)

print(f"\nMonthly Return Distribution:")
print(f"  Portfolio - Mean: {monthly_port.mean() * 100:.2f}%, Median: {monthly_port.median() * 100:.2f}%, StdDev: {monthly_port.std() * 100:.2f}%")
print(f"  SPY      - Mean: {monthly_bench.mean() * 100:.2f}%, Median: {monthly_bench.median() * 100:.2f}%, StdDev: {monthly_bench.std() * 100:.2f}%")
print(f"  Win Rate vs SPY: {(monthly_port > monthly_bench).mean() * 100:.1f}%")

# ============================================================================
# 5. Factor Exposure Analysis
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4: FACTOR EXPOSURE ANALYSIS")
print("=" * 80)

# Multi-factor regression for the portfolio
factor_tickers = ["SPY", "IWM", "IWD", "MTUM"]
available_factors = [f for f in factor_tickers if f in returns.columns]

print("\n--- Equal-Weight Portfolio Factor Decomposition ---")
print(f"Factors: {available_factors}")

y = port_returns
X = sm.add_constant(returns[available_factors])
model = sm.OLS(y, X).fit()

print(f"\nR-squared: {model.rsquared:.4f} (factors explain {model.rsquared * 100:.1f}% of portfolio variance)")
print(f"Adj. R-squared: {model.rsquared_adj:.4f}")
print(f"\nAlpha (annualized): {model.params.iloc[0] * 252 * 100:.2f}% (t-stat: {model.tvalues.iloc[0]:.2f}, p-value: {model.pvalues.iloc[0]:.4f})")

print(f"\n{'Factor':<12} {'Beta':>8} {'t-stat':>8} {'p-value':>10} {'Significance'}")
print("-" * 50)
for i, factor in enumerate(available_factors, 1):
    sig = "***" if model.pvalues.iloc[i] < 0.01 else "**" if model.pvalues.iloc[i] < 0.05 else "*" if model.pvalues.iloc[i] < 0.10 else ""
    print(f"{factor:<12} {model.params.iloc[i]:>8.4f} {model.tvalues.iloc[i]:>8.2f} {model.pvalues.iloc[i]:>10.4f} {sig}")

print(f"\nResidual (idiosyncratic) volatility: {model.resid.std() * np.sqrt(252) * 100:.2f}%")

# Individual stock factor exposures
print("\n--- Individual Stock Market Betas ---")
print(f"\n{'Ticker':<8} {'Market Beta':>12} {'t-stat':>8} {'R²':>8} {'Alpha (%/yr)':>14}")
print("-" * 52)
for ticker in MAG7:
    y_i = returns[ticker]
    X_i = sm.add_constant(returns["SPY"])
    m = sm.OLS(y_i, X_i).fit()
    print(f"{ticker:<8} {m.params.iloc[1]:>12.3f} {m.tvalues.iloc[1]:>8.2f} {m.rsquared:>8.3f} {m.params.iloc[0] * 252 * 100:>13.2f}%")

# ============================================================================
# 6. VaR/CVaR Risk Assessment
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 5: VALUE-AT-RISK & TAIL RISK ASSESSMENT")
print("=" * 80)

confidence_levels = [0.95, 0.99]

print("\n--- Portfolio VaR/CVaR (1-day horizon) ---")
print(f"\n{'Confidence':<14} {'Historical VaR':>15} {'Historical CVaR':>16} {'Parametric VaR':>15} {'Parametric CVaR':>16}")
print("-" * 78)

mu_p = port_returns.mean()
sigma_p = port_returns.std()

for cl in confidence_levels:
    alpha = 1 - cl
    # Historical
    hist_var = np.percentile(port_returns, alpha * 100)
    hist_cvar = port_returns[port_returns <= hist_var].mean()
    # Parametric
    z = stats.norm.ppf(alpha)
    param_var = mu_p + z * sigma_p
    param_cvar = mu_p - sigma_p * stats.norm.pdf(z) / alpha

    print(f"{cl * 100:>5.0f}%        {hist_var * 100:>14.3f}% {hist_cvar * 100:>15.3f}% {param_var * 100:>14.3f}% {param_cvar * 100:>15.3f}%")

print(f"\n--- Tail Risk Metrics ---")
print(f"Worst day:          {port_returns.min() * 100:.3f}%")
print(f"Best day:           {port_returns.max() * 100:.3f}%")
print(f"Negative days:      {(port_returns < 0).mean() * 100:.1f}%")
print(f"Skewness:           {port_returns.skew():.3f}", end="")
print(f"  {'(LEFT TAIL RISK)' if port_returns.skew() < -0.5 else '(moderate)' if port_returns.skew() < 0 else '(positive skew)'}")
print(f"Excess kurtosis:    {port_returns.kurtosis():.3f}", end="")
print(f"  {'(FAT TAILS - WARNING)' if port_returns.kurtosis() > 3 else '(moderate fat tails)' if port_returns.kurtosis() > 1 else '(near-normal)'}")

# Jarque-Bera test
jb_stat, jb_p = stats.jarque_bera(port_returns)
print(f"Jarque-Bera test:   stat={jb_stat:.1f}, p={jb_p:.4f}", end="")
print(f"  {'(REJECT normality)' if jb_p < 0.05 else '(fail to reject normality)'}")

# Compare historical vs parametric
hist_var_99 = np.percentile(port_returns, 1)
param_var_99 = mu_p + stats.norm.ppf(0.01) * sigma_p
ratio = hist_var_99 / param_var_99 if param_var_99 != 0 else 0
print(f"\nHistorical/Parametric VaR(99%) ratio: {ratio:.2f}", end="")
if ratio > 1.3:
    print("  (tails fatter than normal distribution predicts)")
elif ratio < 0.7:
    print("  (recent history understates tail risk)")
else:
    print("  (roughly consistent with normal)")

# Individual stock risk comparison
print(f"\n--- Individual Stock VaR(99%) Comparison ---")
print(f"\n{'Ticker':<8} {'Daily VaR(99%)':>15} {'Max Drawdown':>14} {'Skewness':>10} {'Kurtosis':>10}")
print("-" * 58)
for ticker in MAG7:
    r = returns[ticker]
    close = prices[ticker]
    var99 = np.percentile(r, 1)
    max_dd = (close / close.cummax() - 1).min()
    print(f"{ticker:<8} {var99 * 100:>14.3f}% {max_dd * 100:>13.1f}% {r.skew():>10.3f} {r.kurtosis():>10.3f}")

# ============================================================================
# 7. Conclusions
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 6: CONCLUSIONS & INVESTMENT IMPLICATIONS")
print("=" * 80)

print("""
KEY FINDINGS:

1. RETURN DISPERSION
   The Magnificent 7 show significant return dispersion, ranging from
   high-growth names (NVDA) to more volatile, lower-Sharpe names (TSLA).
   This suggests stock selection matters significantly within this group.

2. CORRELATION STRUCTURE""")
print(f"   Average pairwise correlation is {avg_corr:.2f}.", end="")
if avg_corr > 0.5:
    print(" This is HIGH — these stocks provide")
    print("   limited diversification benefit when combined. A market-wide tech selloff")
    print("   would hit all positions simultaneously.")
else:
    print(" This provides moderate diversification benefit.")

print(f"""
3. PORTFOLIO PERFORMANCE
   Equal-weight Mag 7 portfolio: Sharpe {p_sharpe:.2f} vs SPY Sharpe {b_sharpe:.2f}
   Beta of {beta:.2f} means the portfolio amplifies market moves by ~{beta:.0f}x.
   Tracking error of {tracking_error * 100:.1f}% indicates significant active risk.""")

alpha_sig = "STATISTICALLY SIGNIFICANT" if model.pvalues.iloc[0] < 0.05 else "NOT statistically significant"
print(f"   Alpha of {model.params.iloc[0] * 252 * 100:.2f}% is {alpha_sig} (p={model.pvalues.iloc[0]:.3f}).")

print(f"""
4. FACTOR EXPOSURES
   R² of {model.rsquared:.2f} means {model.rsquared * 100:.0f}% of portfolio returns are explained by factors.
   The remaining {(1 - model.rsquared) * 100:.0f}% is idiosyncratic (stock-specific) risk.
   Primary exposure is to the broad market (SPY beta).""")

print(f"""
5. TAIL RISK
   Portfolio returns show {'significant fat tails' if port_returns.kurtosis() > 3 else 'moderate fat tails'} (kurtosis: {port_returns.kurtosis():.2f}).
   Historical VaR is {'more extreme' if ratio > 1.1 else 'consistent with'} {'than' if ratio > 1.1 else ''} parametric estimates,
   {'confirming non-normal tail behavior.' if ratio > 1.1 else 'suggesting roughly normal tail behavior.'}""")

# Risk flags
print("\nRISK FLAGS:")
flags = []
if p_max_dd * 100 < -25:
    flags.append(f"  [!] Max drawdown of {p_max_dd * 100:.1f}% exceeds 25% threshold")
if p_ann_vol * 100 > 30:
    flags.append(f"  [!] Annualized volatility of {p_ann_vol * 100:.1f}% exceeds 30% threshold")
if p_sharpe < 0.3:
    flags.append(f"  [!] Sharpe ratio of {p_sharpe:.2f} below 0.3 minimum")
if port_returns.skew() < -1.0:
    flags.append(f"  [!] Negative skewness of {port_returns.skew():.2f} indicates left tail risk")
if port_returns.kurtosis() > 5.0:
    flags.append(f"  [!] Excess kurtosis of {port_returns.kurtosis():.2f} indicates extreme fat tails")
if avg_corr > 0.6:
    flags.append(f"  [!] Average correlation of {avg_corr:.2f} indicates poor diversification")

if flags:
    for f in flags:
        print(f)
else:
    print("  No risk flags triggered.")

print(f"""
RECOMMENDATIONS:
  - Consider adding uncorrelated assets (bonds, commodities) to reduce portfolio beta
  - Monitor concentration risk — NVDA alone contributes outsized volatility
  - TSLA's high volatility and lower Sharpe suggest potential for risk reduction via underweighting
  - The high correlation structure makes this portfolio vulnerable to tech sector drawdowns
  - Consider a market-neutral overlay to harvest alpha while reducing directional exposure

{"=" * 80}
END OF REPORT
{"=" * 80}
""")
