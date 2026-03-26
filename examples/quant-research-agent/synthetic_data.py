"""Generate realistic synthetic market data for quantitative research.

When Yahoo Finance is unavailable (e.g., sandboxed environments), this module
provides synthetic price data that preserves realistic statistical properties:
- Correct cross-asset correlations
- Fat-tailed return distributions
- Volatility clustering (GARCH-like)
- Sector-driven co-movement patterns
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Realistic parameters calibrated from historical data (approximate)
ASSET_PARAMS = {
    # Magnificent 7
    "AAPL":  {"mu": 0.20, "sigma": 0.28, "beta": 1.15, "sector": "tech"},
    "MSFT":  {"mu": 0.22, "sigma": 0.27, "beta": 1.10, "sector": "tech"},
    "GOOGL": {"mu": 0.18, "sigma": 0.30, "beta": 1.12, "sector": "tech"},
    "AMZN":  {"mu": 0.16, "sigma": 0.33, "beta": 1.20, "sector": "tech"},
    "NVDA":  {"mu": 0.45, "sigma": 0.55, "beta": 1.80, "sector": "semi"},
    "META":  {"mu": 0.25, "sigma": 0.40, "beta": 1.30, "sector": "tech"},
    "TSLA":  {"mu": 0.15, "sigma": 0.60, "beta": 1.90, "sector": "auto"},
    # Benchmarks & Factors
    "SPY":   {"mu": 0.10, "sigma": 0.16, "beta": 1.00, "sector": "market"},
    "IWM":   {"mu": 0.08, "sigma": 0.22, "beta": 1.20, "sector": "market"},
    "IWD":   {"mu": 0.09, "sigma": 0.18, "beta": 0.95, "sector": "market"},
    "IWF":   {"mu": 0.14, "sigma": 0.20, "beta": 1.05, "sector": "market"},
    "MTUM":  {"mu": 0.12, "sigma": 0.19, "beta": 1.00, "sector": "market"},
    "QUAL":  {"mu": 0.11, "sigma": 0.17, "beta": 0.95, "sector": "market"},
    "USMV":  {"mu": 0.09, "sigma": 0.13, "beta": 0.70, "sector": "market"},
    "TLT":   {"mu": 0.02, "sigma": 0.16, "beta": -0.30, "sector": "bond"},
    "GLD":   {"mu": 0.08, "sigma": 0.15, "beta": 0.05, "sector": "commodity"},
    # Semiconductors
    "AMD":   {"mu": 0.30, "sigma": 0.50, "beta": 1.70, "sector": "semi"},
    "INTC":  {"mu": -0.05, "sigma": 0.38, "beta": 1.10, "sector": "semi"},
    "QCOM":  {"mu": 0.15, "sigma": 0.35, "beta": 1.30, "sector": "semi"},
    "AVGO":  {"mu": 0.35, "sigma": 0.32, "beta": 1.25, "sector": "semi"},
    # Sector ETFs
    "XLK":   {"mu": 0.18, "sigma": 0.22, "beta": 1.15, "sector": "tech"},
    "XLF":   {"mu": 0.10, "sigma": 0.20, "beta": 1.10, "sector": "finance"},
    "XLE":   {"mu": 0.08, "sigma": 0.28, "beta": 0.90, "sector": "energy"},
    "XLV":   {"mu": 0.09, "sigma": 0.16, "beta": 0.75, "sector": "health"},
    "XLY":   {"mu": 0.12, "sigma": 0.22, "beta": 1.10, "sector": "consumer"},
    "XLP":   {"mu": 0.07, "sigma": 0.13, "beta": 0.60, "sector": "staples"},
    "XLU":   {"mu": 0.06, "sigma": 0.16, "beta": 0.40, "sector": "utilities"},
    "XLRE":  {"mu": 0.07, "sigma": 0.20, "beta": 0.80, "sector": "real_estate"},
    "XLI":   {"mu": 0.10, "sigma": 0.19, "beta": 1.05, "sector": "industrial"},
    "XLB":   {"mu": 0.08, "sigma": 0.22, "beta": 1.00, "sector": "materials"},
    "XLC":   {"mu": 0.14, "sigma": 0.24, "beta": 1.10, "sector": "tech"},
    # Other
    "ARKK":  {"mu": 0.05, "sigma": 0.45, "beta": 1.60, "sector": "tech"},
}

SECTOR_CORRELATIONS = {
    ("tech", "tech"): 0.70,
    ("tech", "semi"): 0.65,
    ("tech", "market"): 0.85,
    ("tech", "auto"): 0.45,
    ("tech", "bond"): -0.20,
    ("tech", "commodity"): 0.10,
    ("tech", "finance"): 0.55,
    ("tech", "energy"): 0.30,
    ("tech", "health"): 0.50,
    ("tech", "consumer"): 0.60,
    ("tech", "staples"): 0.35,
    ("tech", "utilities"): 0.20,
    ("tech", "real_estate"): 0.40,
    ("tech", "industrial"): 0.55,
    ("tech", "materials"): 0.45,
    ("semi", "semi"): 0.75,
    ("semi", "market"): 0.75,
    ("semi", "auto"): 0.50,
    ("semi", "bond"): -0.15,
    ("semi", "commodity"): 0.15,
    ("market", "market"): 0.90,
    ("market", "auto"): 0.55,
    ("market", "bond"): -0.25,
    ("market", "commodity"): 0.15,
    ("market", "finance"): 0.80,
    ("market", "energy"): 0.60,
    ("market", "health"): 0.70,
    ("market", "consumer"): 0.75,
    ("market", "staples"): 0.55,
    ("market", "utilities"): 0.40,
    ("market", "real_estate"): 0.60,
    ("market", "industrial"): 0.80,
    ("market", "materials"): 0.70,
    ("auto", "auto"): 0.60,
    ("auto", "bond"): -0.10,
    ("auto", "commodity"): 0.20,
    ("bond", "bond"): 0.85,
    ("bond", "commodity"): 0.15,
    ("commodity", "commodity"): 0.70,
    ("finance", "finance"): 0.75,
    ("energy", "energy"): 0.80,
    ("health", "health"): 0.65,
    ("consumer", "consumer"): 0.70,
    ("staples", "staples"): 0.65,
    ("utilities", "utilities"): 0.70,
    ("real_estate", "real_estate"): 0.70,
    ("industrial", "industrial"): 0.75,
    ("materials", "materials"): 0.70,
}


def _get_sector_corr(s1: str, s2: str) -> float:
    """Get correlation between two sectors."""
    if s1 == s2:
        return SECTOR_CORRELATIONS.get((s1, s2), 0.60)
    key = (min(s1, s2), max(s1, s2)) if (min(s1, s2), max(s1, s2)) in SECTOR_CORRELATIONS else (s1, s2)
    return SECTOR_CORRELATIONS.get(key, SECTOR_CORRELATIONS.get((s2, s1), 0.40))


def generate_price_data(
    tickers: list[str],
    n_days: int = 756,  # ~3 years
    seed: int = 42,
) -> pd.DataFrame:
    """Generate correlated price series with realistic statistical properties.

    Args:
        tickers: List of ticker symbols (must be in ASSET_PARAMS).
        n_days: Number of trading days to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with DatetimeIndex and columns for each ticker's Close price.
    """
    rng = np.random.default_rng(seed)
    n = len(tickers)

    # Build correlation matrix from sector relationships
    params = [ASSET_PARAMS.get(t, {"mu": 0.10, "sigma": 0.20, "beta": 1.0, "sector": "market"}) for t in tickers]

    corr_matrix = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            base_corr = _get_sector_corr(params[i]["sector"], params[j]["sector"])
            # Add beta-driven correlation boost
            beta_adj = 0.1 * min(params[i]["beta"], params[j]["beta"])
            corr = min(0.95, base_corr + beta_adj + rng.normal(0, 0.03))
            corr_matrix[i, j] = corr
            corr_matrix[j, i] = corr

    # Ensure positive semi-definite
    eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)
    eigenvalues = np.maximum(eigenvalues, 1e-6)
    corr_matrix = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    # Normalize back to correlation matrix
    d = np.sqrt(np.diag(corr_matrix))
    corr_matrix = corr_matrix / np.outer(d, d)

    # Cholesky decomposition for correlated normals
    L = np.linalg.cholesky(corr_matrix)

    # Generate returns with volatility clustering
    daily_returns = np.zeros((n_days, n))
    vol_state = np.ones(n)  # Current volatility multiplier

    for t in range(n_days):
        # GARCH-like volatility dynamics
        z = rng.standard_normal(n)
        correlated_z = L @ z

        # Add fat tails via t-distribution mixing
        t_noise = rng.standard_t(df=5, size=n) * 0.3
        innovations = correlated_z * 0.7 + t_noise * 0.3

        for i in range(n):
            daily_mu = params[i]["mu"] / 252
            daily_sigma = params[i]["sigma"] / np.sqrt(252) * vol_state[i]

            daily_returns[t, i] = daily_mu + daily_sigma * innovations[i]

            # Update volatility state (mean-reverting)
            vol_state[i] = 0.94 * vol_state[i] + 0.06 * (1 + abs(innovations[i]) * 0.5)

    # Convert to prices
    prices = np.zeros((n_days, n))
    for i in range(n):
        # Start prices at realistic levels
        start_prices = {
            "AAPL": 150, "MSFT": 300, "GOOGL": 130, "AMZN": 140, "NVDA": 250,
            "META": 300, "TSLA": 200, "SPY": 430, "IWM": 190, "IWD": 160,
            "IWF": 280, "MTUM": 170, "QUAL": 140, "USMV": 75, "TLT": 100,
            "GLD": 180, "AMD": 120, "INTC": 35, "QCOM": 140, "AVGO": 800,
            "XLK": 170, "XLF": 35, "XLE": 80, "XLV": 140, "XLY": 170,
            "XLP": 75, "XLU": 65, "XLRE": 40, "XLI": 105, "XLB": 80,
            "XLC": 65, "ARKK": 40,
        }
        p0 = start_prices.get(tickers[i], 100)
        prices[:, i] = p0 * np.exp(np.cumsum(daily_returns[:, i]))

    # Build DataFrame
    dates = pd.bdate_range(end="2026-03-25", periods=n_days)
    df = pd.DataFrame(prices, index=dates, columns=tickers)
    df.index.name = "Date"

    return df


def period_to_days(period: str) -> int:
    """Convert period string to approximate trading days."""
    mapping = {
        "1mo": 21, "3mo": 63, "6mo": 126,
        "1y": 252, "2y": 504, "3y": 756,
        "5y": 1260, "10y": 2520, "max": 2520,
    }
    return mapping.get(period, 504)
