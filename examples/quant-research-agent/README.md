# Quantitative Research Agent

A data-driven quantitative finance research agent built on Deep Agents. Conducts rigorous statistical analysis of financial markets using real market data.

## Features

- **Real market data** via Yahoo Finance (no API key needed)
- **Factor analysis** with OLS regression against ETF proxies
- **Portfolio backtesting** with long/short support and benchmark comparison
- **Risk assessment** with VaR, CVaR, drawdown analysis, and tail metrics
- **Universe screening** by Sharpe ratio, volatility, returns
- **3 specialized subagents** for parallel research: data analyst, strategy researcher, risk analyst

## Quickstart

```bash
# Install dependencies
uv sync

# Set your API key
export ANTHROPIC_API_KEY=your-key-here

# Run with default research query (Magnificent 7 analysis)
uv run python agent.py

# Run with custom query
uv run python agent.py "Compare momentum vs value factor performance over the last 5 years"
```

## Tools

| Tool | Description |
|------|-------------|
| `fetch_price_data` | Historical OHLCV data with summary statistics |
| `compute_correlation_matrix` | Return correlations (Pearson, Spearman, Kendall) |
| `compute_rolling_statistics` | Rolling return, volatility, Sharpe at multiple windows |
| `run_factor_regression` | OLS factor model with alpha, betas, R-squared |
| `backtest_strategy` | Long/short portfolio backtest with benchmark comparison |
| `compute_var_cvar` | Value-at-Risk and Expected Shortfall (historical + parametric) |
| `screen_universe` | Filter and rank assets by risk/return metrics |

## Architecture

```
Orchestrator Agent (Claude)
    |
    +-- data-analyst subagent
    |     Tools: fetch_price_data, correlation, rolling stats, screening
    |
    +-- strategy-researcher subagent
    |     Tools: backtest, factor regression, screening
    |
    +-- risk-analyst subagent
          Tools: VaR/CVaR, correlation, rolling stats
```

## Example Research Queries

- "Analyze the risk-adjusted performance of semiconductor stocks (NVDA, AMD, INTC, QCOM, AVGO)"
- "Build a minimum-volatility portfolio from S&P 500 sector ETFs"
- "What are the factor exposures of ARK Innovation ETF (ARKK)?"
- "Compare gold (GLD) vs bonds (TLT) as portfolio hedges during equity drawdowns"
- "Screen the FAANG stocks and build an equal-weight portfolio backtest"

## Customization

- Edit `AGENTS.md` to change research methodology and reporting standards
- Add new skills in `skills/` for custom analysis workflows
- Modify subagent definitions in `agent.py` for different specializations
- Add custom tools in `tools.py` for additional data sources
