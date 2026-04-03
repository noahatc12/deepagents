"""Quantitative research tools for financial analysis."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Annotated

import numpy as np
import pandas as pd
import yfinance as yf
from langchain_core.tools import tool


@tool
def fetch_price_data(
    tickers: Annotated[list[str], "List of ticker symbols (e.g., ['AAPL', 'MSFT'])"],
    period: Annotated[str, "Time period: '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'max'"] = "2y",
    interval: Annotated[str, "Data interval: '1d', '1wk', '1mo'"] = "1d",
) -> str:
    """Fetch historical OHLCV price data for one or more tickers from Yahoo Finance.

    Returns a JSON summary with statistics and the most recent rows of data.
    """
    try:
        data = yf.download(tickers, period=period, interval=interval, group_by="ticker", progress=False)
    except Exception as e:
        return f"Error fetching data: {e}"

    if data.empty:
        return "No data returned. Check ticker symbols and period."

    results = {}
    ticker_list = tickers if isinstance(tickers, list) else [tickers]

    for ticker in ticker_list:
        try:
            if len(ticker_list) == 1:
                df = data
            else:
                df = data[ticker]

            close = df["Close"].dropna()
            if close.empty:
                results[ticker] = "No price data available"
                continue

            returns = close.pct_change().dropna()

            results[ticker] = {
                "data_points": len(close),
                "date_range": f"{close.index[0].strftime('%Y-%m-%d')} to {close.index[-1].strftime('%Y-%m-%d')}",
                "latest_price": round(float(close.iloc[-1]), 2),
                "period_return_pct": round(float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2),
                "annualized_return_pct": round(float(returns.mean() * 252 * 100), 2),
                "annualized_volatility_pct": round(float(returns.std() * np.sqrt(252) * 100), 2),
                "sharpe_ratio": round(float(returns.mean() / returns.std() * np.sqrt(252)), 3) if returns.std() > 0 else None,
                "max_drawdown_pct": round(float((close / close.cummax() - 1).min() * 100), 2),
                "skewness": round(float(returns.skew()), 3),
                "kurtosis": round(float(returns.kurtosis()), 3),
                "recent_prices": {
                    d.strftime("%Y-%m-%d"): round(float(v), 2)
                    for d, v in close.tail(5).items()
                },
            }
        except Exception as e:
            results[ticker] = f"Error processing {ticker}: {e}"

    return json.dumps(results, indent=2)


@tool
def compute_correlation_matrix(
    tickers: Annotated[list[str], "List of ticker symbols"],
    period: Annotated[str, "Time period for analysis"] = "2y",
    method: Annotated[str, "'pearson', 'spearman', or 'kendall'"] = "pearson",
) -> str:
    """Compute the return correlation matrix for a set of assets.

    Useful for portfolio diversification analysis and understanding co-movement.
    """
    try:
        data = yf.download(tickers, period=period, progress=False)["Close"]
    except Exception as e:
        return f"Error fetching data: {e}"

    if data.empty:
        return "No data returned."

    returns = data.pct_change().dropna()
    corr = returns.corr(method=method)

    result = {
        "method": method,
        "period": period,
        "num_observations": len(returns),
        "correlation_matrix": {
            str(i): {str(j): round(float(corr.loc[i, j]), 4) for j in corr.columns}
            for i in corr.index
        },
    }

    # Identify strongest and weakest correlations (excluding self)
    pairs = []
    for i in range(len(corr)):
        for j in range(i + 1, len(corr)):
            pairs.append({
                "pair": f"{corr.index[i]}-{corr.columns[j]}",
                "correlation": round(float(corr.iloc[i, j]), 4),
            })

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    result["strongest_pairs"] = pairs[:3]
    result["weakest_pairs"] = sorted(pairs, key=lambda x: abs(x["correlation"]))[:3]

    return json.dumps(result, indent=2)


@tool
def compute_rolling_statistics(
    ticker: Annotated[str, "Ticker symbol"],
    windows: Annotated[list[int], "Rolling window sizes in trading days (e.g., [21, 63, 252])"] = [21, 63, 252],
    period: Annotated[str, "Time period for data"] = "5y",
) -> str:
    """Compute rolling return, volatility, and Sharpe ratio for a single asset.

    Default windows: 21 (1 month), 63 (1 quarter), 252 (1 year).
    """
    try:
        data = yf.download(ticker, period=period, progress=False)
    except Exception as e:
        return f"Error fetching data: {e}"

    close = data["Close"].dropna()
    if close.empty:
        return f"No data for {ticker}"

    returns = close.pct_change().dropna()
    results = {"ticker": ticker, "data_points": len(close), "windows": {}}

    for w in windows:
        if len(returns) < w:
            results["windows"][f"{w}d"] = f"Insufficient data (need {w}, have {len(returns)})"
            continue

        roll_ret = returns.rolling(w).mean() * 252
        roll_vol = returns.rolling(w).std() * np.sqrt(252)
        roll_sharpe = roll_ret / roll_vol

        latest = {
            "annualized_return_pct": round(float(roll_ret.iloc[-1] * 100), 2),
            "annualized_volatility_pct": round(float(roll_vol.iloc[-1] * 100), 2),
            "sharpe_ratio": round(float(roll_sharpe.iloc[-1]), 3),
        }

        percentiles = {
            "return_percentile": round(float((roll_ret < roll_ret.iloc[-1]).mean() * 100), 1),
            "volatility_percentile": round(float((roll_vol < roll_vol.iloc[-1]).mean() * 100), 1),
        }

        results["windows"][f"{w}d"] = {
            "current": latest,
            "percentiles_vs_history": percentiles,
            "return_range": {
                "min_pct": round(float(roll_ret.min() * 100), 2),
                "max_pct": round(float(roll_ret.max() * 100), 2),
            },
            "volatility_range": {
                "min_pct": round(float(roll_vol.min() * 100), 2),
                "max_pct": round(float(roll_vol.max() * 100), 2),
            },
        }

    return json.dumps(results, indent=2)


@tool
def run_factor_regression(
    ticker: Annotated[str, "Ticker symbol to analyze"],
    factors: Annotated[list[str], "Factor proxy tickers (e.g., ['SPY'] for market, ['IWM'] for size)"],
    period: Annotated[str, "Time period"] = "3y",
) -> str:
    """Run a factor regression (OLS) of asset returns on factor returns.

    This is a simplified factor model using ETF proxies. For example:
    - SPY = market factor
    - IWM-SPY = size factor (small minus large)
    - IWD-IWF = value factor (value minus growth)
    - TLT = interest rate sensitivity

    Returns alpha, betas, R-squared, and residual analysis.
    """
    import statsmodels.api as sm

    all_tickers = [ticker] + factors
    try:
        data = yf.download(all_tickers, period=period, progress=False)["Close"]
    except Exception as e:
        return f"Error fetching data: {e}"

    if data.empty:
        return "No data returned."

    returns = data.pct_change().dropna()

    if ticker not in returns.columns:
        return f"No data for {ticker}"

    y = returns[ticker]
    x_cols = [f for f in factors if f in returns.columns]
    if not x_cols:
        return "No valid factor data found."

    X = sm.add_constant(returns[x_cols])
    model = sm.OLS(y, X).fit()

    result = {
        "ticker": ticker,
        "factors": x_cols,
        "num_observations": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4),
        "adj_r_squared": round(float(model.rsquared_adj), 4),
        "alpha_annualized_pct": round(float(model.params.iloc[0] * 252 * 100), 3),
        "alpha_t_stat": round(float(model.tvalues.iloc[0]), 3),
        "alpha_p_value": round(float(model.pvalues.iloc[0]), 4),
        "betas": {},
        "residual_stats": {
            "annualized_vol_pct": round(float(model.resid.std() * np.sqrt(252) * 100), 2),
            "skewness": round(float(model.resid.skew()), 3),
            "kurtosis": round(float(model.resid.kurtosis()), 3),
        },
    }

    for i, factor in enumerate(x_cols, 1):
        result["betas"][factor] = {
            "beta": round(float(model.params.iloc[i]), 4),
            "t_stat": round(float(model.tvalues.iloc[i]), 3),
            "p_value": round(float(model.pvalues.iloc[i]), 4),
        }

    return json.dumps(result, indent=2)


@tool
def backtest_strategy(
    long_tickers: Annotated[list[str], "Tickers to go long"],
    long_weights: Annotated[list[float], "Portfolio weights for long positions (must sum to <= 1.0)"],
    benchmark: Annotated[str, "Benchmark ticker for comparison (e.g., 'SPY')"] = "SPY",
    period: Annotated[str, "Backtest period"] = "5y",
    rebalance: Annotated[str, "'daily', 'monthly', or 'quarterly'"] = "monthly",
    short_tickers: Annotated[list[str] | None, "Optional tickers to short"] = None,
    short_weights: Annotated[list[float] | None, "Weights for short positions (positive values)"] = None,
) -> str:
    """Backtest a long/short portfolio strategy against a benchmark.

    Computes cumulative returns, risk metrics, and performance attribution.
    Weights should be positive; short_weights are applied as negative positions.
    """
    all_tickers = list(long_tickers)
    if short_tickers:
        all_tickers.extend(short_tickers)
    if benchmark not in all_tickers:
        all_tickers.append(benchmark)

    try:
        data = yf.download(all_tickers, period=period, progress=False)["Close"]
    except Exception as e:
        return f"Error fetching data: {e}"

    if data.empty:
        return "No data returned."

    returns = data.pct_change().dropna()

    # Build portfolio weights
    weights = {}
    for t, w in zip(long_tickers, long_weights):
        if t in returns.columns:
            weights[t] = w
    if short_tickers and short_weights:
        for t, w in zip(short_tickers, short_weights):
            if t in returns.columns:
                weights[t] = -w

    if not weights:
        return "No valid tickers in the portfolio."

    # Compute portfolio returns
    port_returns = sum(returns[t] * w for t, w in weights.items())
    bench_returns = returns[benchmark] if benchmark in returns.columns else None

    # Rebalancing simulation (simplified - assumes daily rebalance for now)
    cumulative = (1 + port_returns).cumprod()
    bench_cumulative = (1 + bench_returns).cumprod() if bench_returns is not None else None

    # Compute metrics
    ann_ret = float(port_returns.mean() * 252)
    ann_vol = float(port_returns.std() * np.sqrt(252))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    max_dd = float((cumulative / cumulative.cummax() - 1).min())
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

    result = {
        "portfolio": {
            "weights": {t: round(w, 4) for t, w in weights.items()},
            "net_exposure": round(sum(weights.values()), 4),
            "gross_exposure": round(sum(abs(w) for w in weights.values()), 4),
        },
        "performance": {
            "total_return_pct": round(float((cumulative.iloc[-1] - 1) * 100), 2),
            "annualized_return_pct": round(ann_ret * 100, 2),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "skewness": round(float(port_returns.skew()), 3),
            "kurtosis": round(float(port_returns.kurtosis()), 3),
        },
        "period": {
            "start": port_returns.index[0].strftime("%Y-%m-%d"),
            "end": port_returns.index[-1].strftime("%Y-%m-%d"),
            "trading_days": len(port_returns),
        },
    }

    if bench_returns is not None:
        bench_ann_ret = float(bench_returns.mean() * 252)
        bench_ann_vol = float(bench_returns.std() * np.sqrt(252))
        bench_sharpe = bench_ann_ret / bench_ann_vol if bench_ann_vol > 0 else 0
        bench_max_dd = float((bench_cumulative / bench_cumulative.cummax() - 1).min())

        # Tracking error and information ratio
        active_returns = port_returns - bench_returns
        tracking_error = float(active_returns.std() * np.sqrt(252))
        info_ratio = float(active_returns.mean() * 252 / tracking_error) if tracking_error > 0 else 0

        # Beta and correlation
        cov = np.cov(port_returns, bench_returns)
        beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0
        correlation = float(np.corrcoef(port_returns, bench_returns)[0, 1])

        result["benchmark"] = {
            "ticker": benchmark,
            "total_return_pct": round(float((bench_cumulative.iloc[-1] - 1) * 100), 2),
            "annualized_return_pct": round(bench_ann_ret * 100, 2),
            "annualized_volatility_pct": round(bench_ann_vol * 100, 2),
            "sharpe_ratio": round(bench_sharpe, 3),
            "max_drawdown_pct": round(bench_max_dd * 100, 2),
        }
        result["relative"] = {
            "excess_return_pct": round((ann_ret - bench_ann_ret) * 100, 2),
            "tracking_error_pct": round(tracking_error * 100, 2),
            "information_ratio": round(info_ratio, 3),
            "beta": round(beta, 3),
            "correlation": round(correlation, 4),
            "alpha_pct": round((ann_ret - beta * bench_ann_ret) * 100, 2),
        }

    # Monthly returns table (last 12 months)
    monthly_ret = port_returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    result["monthly_returns_pct"] = {
        d.strftime("%Y-%m"): round(float(v * 100), 2)
        for d, v in monthly_ret.tail(12).items()
    }

    return json.dumps(result, indent=2)


@tool
def compute_var_cvar(
    tickers: Annotated[list[str], "Ticker symbols in the portfolio"],
    weights: Annotated[list[float], "Portfolio weights"],
    confidence_levels: Annotated[list[float], "Confidence levels (e.g., [0.95, 0.99])"] = [0.95, 0.99],
    period: Annotated[str, "Historical period for estimation"] = "3y",
    horizon_days: Annotated[int, "VaR horizon in trading days"] = 1,
) -> str:
    """Compute Value-at-Risk (VaR) and Conditional VaR (CVaR/Expected Shortfall).

    Uses both historical simulation and parametric (normal) methods.
    Results are expressed as percentage losses.
    """
    try:
        data = yf.download(tickers, period=period, progress=False)["Close"]
    except Exception as e:
        return f"Error: {e}"

    if data.empty:
        return "No data returned."

    returns = data.pct_change().dropna()

    # Portfolio returns
    valid_weights = {}
    for t, w in zip(tickers, weights):
        if t in returns.columns:
            valid_weights[t] = w

    if not valid_weights:
        return "No valid tickers."

    port_returns = sum(returns[t] * w for t, w in valid_weights.items())

    # Scale to horizon
    if horizon_days > 1:
        port_returns = port_returns.rolling(horizon_days).sum().dropna()

    result = {
        "portfolio_weights": {t: round(w, 4) for t, w in valid_weights.items()},
        "horizon_days": horizon_days,
        "num_observations": len(port_returns),
        "risk_measures": {},
    }

    from scipy import stats

    for cl in confidence_levels:
        alpha = 1 - cl

        # Historical VaR
        hist_var = float(np.percentile(port_returns, alpha * 100))
        # Historical CVaR (expected shortfall)
        hist_cvar = float(port_returns[port_returns <= hist_var].mean())

        # Parametric VaR (assumes normality)
        mu = float(port_returns.mean())
        sigma = float(port_returns.std())
        z = stats.norm.ppf(alpha)
        param_var = mu + z * sigma
        # Parametric CVaR
        param_cvar = mu - sigma * stats.norm.pdf(z) / alpha

        result["risk_measures"][f"{int(cl * 100)}%"] = {
            "historical": {
                "var_pct": round(hist_var * 100, 3),
                "cvar_pct": round(hist_cvar * 100, 3),
            },
            "parametric": {
                "var_pct": round(param_var * 100, 3),
                "cvar_pct": round(param_cvar * 100, 3),
            },
        }

    # Additional tail risk metrics
    result["tail_metrics"] = {
        "worst_day_pct": round(float(port_returns.min() * 100), 3),
        "best_day_pct": round(float(port_returns.max() * 100), 3),
        "negative_days_pct": round(float((port_returns < 0).mean() * 100), 1),
        "skewness": round(float(port_returns.skew()), 3),
        "excess_kurtosis": round(float(port_returns.kurtosis()), 3),
        "jarque_bera_p_value": round(float(stats.jarque_bera(port_returns)[1]), 4),
    }

    return json.dumps(result, indent=2)


@tool
def screen_universe(
    tickers: Annotated[list[str], "Tickers to screen"],
    min_sharpe: Annotated[float | None, "Minimum Sharpe ratio filter"] = None,
    max_volatility: Annotated[float | None, "Maximum annualized volatility (decimal, e.g., 0.3 for 30%)"] = None,
    min_return: Annotated[float | None, "Minimum annualized return (decimal)"] = None,
    period: Annotated[str, "Period for computing metrics"] = "1y",
    sort_by: Annotated[str, "'sharpe', 'return', 'volatility', 'drawdown'"] = "sharpe",
) -> str:
    """Screen a universe of assets by risk/return metrics.

    Filters and ranks assets based on Sharpe ratio, volatility, returns, etc.
    Useful for identifying candidates for portfolio construction.
    """
    try:
        data = yf.download(tickers, period=period, progress=False)["Close"]
    except Exception as e:
        return f"Error: {e}"

    if data.empty:
        return "No data returned."

    results = []
    for ticker in tickers:
        if ticker not in data.columns:
            continue

        close = data[ticker].dropna()
        if len(close) < 20:
            continue

        returns = close.pct_change().dropna()
        ann_ret = float(returns.mean() * 252)
        ann_vol = float(returns.std() * np.sqrt(252))
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        max_dd = float((close / close.cummax() - 1).min())

        # Apply filters
        if min_sharpe is not None and sharpe < min_sharpe:
            continue
        if max_volatility is not None and ann_vol > max_volatility:
            continue
        if min_return is not None and ann_ret < min_return:
            continue

        results.append({
            "ticker": ticker,
            "annualized_return_pct": round(ann_ret * 100, 2),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "total_return_pct": round(float((close.iloc[-1] / close.iloc[0] - 1) * 100), 2),
        })

    # Sort
    sort_keys = {
        "sharpe": lambda x: -x["sharpe_ratio"],
        "return": lambda x: -x["annualized_return_pct"],
        "volatility": lambda x: x["annualized_volatility_pct"],
        "drawdown": lambda x: x["max_drawdown_pct"],
    }
    results.sort(key=sort_keys.get(sort_by, sort_keys["sharpe"]))

    output = {
        "filters_applied": {
            "min_sharpe": min_sharpe,
            "max_volatility": max_volatility,
            "min_return": min_return,
        },
        "period": period,
        "sorted_by": sort_by,
        "total_screened": len(tickers),
        "passed_filter": len(results),
        "results": results,
    }

    return json.dumps(output, indent=2)
