---
name: factor-analysis
description: Use this skill when analyzing what drives an asset's returns, decomposing risk exposures, or evaluating factor tilts in a portfolio.
---

# Factor Analysis Workflow

## Step 1: Data Collection
Fetch price data for the target asset and relevant factor proxies using `fetch_price_data`.

Standard factor proxies:
- **Market**: SPY
- **Size**: IWM (small cap proxy)
- **Value**: IWD (value proxy)
- **Momentum**: MTUM
- **Quality**: QUAL
- **Low Volatility**: USMV
- **Bonds**: TLT (duration exposure)

## Step 2: Factor Regression
Run `run_factor_regression` with the target asset against relevant factors.

Key outputs to examine:
- **R-squared**: How much of the asset's variance is explained by factors (>0.7 is high)
- **Alpha**: Annualized excess return after controlling for factors. Check t-stat (>2.0 is significant at 95%)
- **Betas**: Factor loadings. Magnitude indicates exposure strength
- **Residual volatility**: Idiosyncratic risk not captured by factors

## Step 3: Rolling Analysis
Use `compute_rolling_statistics` to check if factor exposures are stable over time.

Look for:
- Regime changes in volatility or returns
- Time-varying factor loadings (structural breaks)
- Current positioning relative to historical range

## Step 4: Interpretation
- Compare betas to category peers
- Assess whether factor tilts are intentional or incidental
- Identify any uncompensated risks (high exposure, low return contribution)
- Flag if alpha is likely due to an unmeasured factor rather than genuine skill
