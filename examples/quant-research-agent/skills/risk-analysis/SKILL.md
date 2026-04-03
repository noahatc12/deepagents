---
name: risk-analysis
description: Use this skill when assessing portfolio risk, computing VaR/CVaR, analyzing tail risk, or stress-testing portfolios.
---

# Risk Analysis Workflow

## Step 1: Baseline Risk Metrics
Fetch data with `fetch_price_data` and compute:
- Annualized volatility
- Maximum drawdown and drawdown duration
- Skewness (negative = left tail risk)
- Kurtosis (>3 = fat tails, more extreme events than normal)

## Step 2: Value-at-Risk Analysis
Use `compute_var_cvar` at 95% and 99% confidence levels.

Interpretation:
- **VaR(95%)**: Loss that will be exceeded on ~1 in 20 days
- **VaR(99%)**: Loss that will be exceeded on ~1 in 100 days
- **CVaR** (Expected Shortfall): Average loss *when* VaR is breached — this is the more important measure

Compare historical vs parametric VaR:
- If historical VaR >> parametric VaR: returns have fat tails (not well-modeled by normal distribution)
- If parametric VaR >> historical VaR: recent history may understate risk

## Step 3: Correlation and Contagion Risk
Use `compute_correlation_matrix` to assess:
- Portfolio diversification (low average correlation = good)
- Correlation clustering (groups of highly correlated assets)
- Tail correlation (do correlations increase in drawdowns?)

## Step 4: Regime Analysis
Use `compute_rolling_statistics` with multiple windows to detect:
- Volatility regimes (low vol vs high vol periods)
- Return regime shifts
- Current regime relative to history (percentile ranking)

## Step 5: Risk Report
Synthesize findings into:
1. **Current risk posture**: Where does the portfolio stand today vs history?
2. **Tail risk assessment**: How bad could a worst-case scenario be?
3. **Diversification quality**: Are positions truly diversified or only apparently so?
4. **Risk recommendations**: Specific actions to improve the risk profile
