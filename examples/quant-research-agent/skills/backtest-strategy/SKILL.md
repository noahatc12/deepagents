---
name: backtest-strategy
description: Use this skill when constructing, testing, or evaluating portfolio strategies against benchmarks.
---

# Strategy Backtesting Workflow

## Step 1: Universe Screening
Use `screen_universe` to filter assets by risk/return characteristics.

Common screens:
- **Quality growth**: min_sharpe=0.5, min_return=0.05
- **Low volatility**: max_volatility=0.15, sort_by="volatility"
- **Momentum**: sort_by="return", period="6mo"

## Step 2: Portfolio Construction
Decide on:
- **Allocation method**: Equal weight, risk parity, or conviction-based
- **Long/short**: Pure long, long-short, or market-neutral
- **Rebalancing**: Monthly is standard; quarterly reduces turnover

For equal-weight long-only with N assets: weight = 1.0 / N

## Step 3: Backtest Execution
Run `backtest_strategy` with your portfolio.

Evaluate the results against these benchmarks:
- **Absolute**: Is the Sharpe ratio > 0.5? Is max drawdown manageable?
- **Relative**: Does it beat the benchmark on risk-adjusted basis (information ratio > 0.3)?
- **Risk**: Is the beta reasonable? Is tracking error intentional?

## Step 4: Robustness Analysis
- Run the same strategy over different periods (bull market, bear market, sideways)
- Check for concentration risk (few stocks driving performance)
- Compute the correlation matrix to verify diversification

## Step 5: Risk Assessment
Use `compute_var_cvar` to assess tail risk.
Use `compute_correlation_matrix` to understand diversification.

Flag strategies that show:
- Max drawdown > 25%
- Negative information ratio
- High correlation to benchmark (>0.95) with lower returns
- Fat tails (excess kurtosis > 5)
