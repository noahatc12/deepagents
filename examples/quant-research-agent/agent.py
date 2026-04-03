"""Quantitative finance research agent with specialized subagents.

This agent conducts rigorous, data-driven financial analysis using real market data.
It has three specialized subagents:
- data-analyst: Fetches data, computes statistics, screens universes
- strategy-researcher: Constructs and backtests portfolio strategies
- risk-analyst: Assesses tail risk, VaR/CVaR, and portfolio stress testing

Usage:
    uv run python agent.py "Analyze the risk-adjusted performance of the Magnificent 7 stocks"
"""

from __future__ import annotations

import asyncio
import sys

from langchain_anthropic import ChatAnthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import SubAgent

from tools import (
    backtest_strategy,
    compute_correlation_matrix,
    compute_rolling_statistics,
    compute_var_cvar,
    fetch_price_data,
    run_factor_regression,
    screen_universe,
)

SYSTEM_PROMPT = """\
You are a senior quantitative researcher at a systematic investment firm.

Your job is to conduct thorough, data-driven financial research using real market data.
You have access to specialized subagents for different aspects of the research process.

When given a research question:
1. Break it down into data collection, analysis, and risk assessment components
2. Delegate to appropriate subagents in parallel where possible
3. Synthesize findings into a coherent research report with clear conclusions

Always use real data — never fabricate numbers. If data is unavailable, say so.
Present results with appropriate statistical context (sample sizes, significance, caveats).
"""

ALL_TOOLS = [
    fetch_price_data,
    compute_correlation_matrix,
    compute_rolling_statistics,
    run_factor_regression,
    backtest_strategy,
    compute_var_cvar,
    screen_universe,
]

DATA_ANALYST_SUBAGENT: SubAgent = {
    "name": "data-analyst",
    "description": (
        "Specialized in fetching market data, computing summary statistics, "
        "correlation analysis, rolling metrics, and screening asset universes. "
        "Use for data gathering, exploratory analysis, and universe construction."
    ),
    "system_prompt": (
        "You are a quantitative data analyst. Your role is to fetch market data, "
        "compute statistics, and present clear, accurate numerical summaries. "
        "Always report the time period, number of observations, and any data quality issues. "
        "Use fetch_price_data, compute_correlation_matrix, compute_rolling_statistics, "
        "and screen_universe tools."
    ),
    "tools": [fetch_price_data, compute_correlation_matrix, compute_rolling_statistics, screen_universe],
}

STRATEGY_RESEARCHER_SUBAGENT: SubAgent = {
    "name": "strategy-researcher",
    "description": (
        "Specialized in constructing and backtesting portfolio strategies, "
        "factor regression analysis, and performance attribution. "
        "Use for building portfolios, running factor models, and comparing strategies to benchmarks."
    ),
    "system_prompt": (
        "You are a quantitative strategy researcher. Your role is to construct portfolios, "
        "run backtests, and perform factor analysis. Always compare strategies against "
        "appropriate benchmarks. Report both absolute and risk-adjusted metrics. "
        "Flag any concerns about overfitting, data snooping, or unrealistic assumptions. "
        "Use backtest_strategy, run_factor_regression, and fetch_price_data tools."
    ),
    "tools": [backtest_strategy, run_factor_regression, fetch_price_data, screen_universe],
}

RISK_ANALYST_SUBAGENT: SubAgent = {
    "name": "risk-analyst",
    "description": (
        "Specialized in portfolio risk assessment including VaR/CVaR, tail risk analysis, "
        "drawdown analysis, and stress testing. "
        "Use for evaluating downside risk, portfolio diversification, and risk recommendations."
    ),
    "system_prompt": (
        "You are a quantitative risk analyst. Your role is to assess portfolio risk using "
        "VaR, CVaR, tail metrics, and correlation analysis. Always distinguish between "
        "historical and parametric estimates. Flag fat tails, correlation clustering, "
        "and concentration risk. Present both current risk posture and worst-case scenarios. "
        "Use compute_var_cvar, compute_correlation_matrix, compute_rolling_statistics, "
        "and fetch_price_data tools."
    ),
    "tools": [compute_var_cvar, compute_correlation_matrix, compute_rolling_statistics, fetch_price_data],
}


def create_quant_agent(model: str = "claude-sonnet-4-6"):
    """Create the quant research agent with all subagents."""
    chat_model = ChatAnthropic(model_name=model)

    return create_deep_agent(
        model=chat_model,
        system_prompt=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        subagents=[
            DATA_ANALYST_SUBAGENT,
            STRATEGY_RESEARCHER_SUBAGENT,
            RISK_ANALYST_SUBAGENT,
        ],
        memory=["./AGENTS.md"],
        skills=["./skills/"],
        backend=FilesystemBackend(root_dir="."),
    )


async def main():
    console = Console()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = (
            "Conduct a comprehensive quantitative analysis of the 'Magnificent 7' tech stocks "
            "(AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA). Include: "
            "1) Individual risk-return profiles, "
            "2) Correlation structure and diversification analysis, "
            "3) An equal-weight portfolio backtest vs SPY, "
            "4) Factor exposures (market, size, value, momentum), "
            "5) VaR/CVaR risk assessment. "
            "Present findings as a structured research report."
        )

    console.print(Panel(query, title="Research Query", border_style="blue"))

    agent = create_quant_agent()

    console.print("\n[bold]Running quantitative research...[/bold]\n")

    result = await agent.ainvoke(
        {"messages": [("user", query)]},
        config={"configurable": {"thread_id": "quant-research-1"}},
    )

    # Extract final response
    final_message = result["messages"][-1]
    if hasattr(final_message, "content") and isinstance(final_message.content, str):
        console.print(Panel(Markdown(final_message.content), title="Research Report", border_style="green"))
    else:
        console.print(final_message)


if __name__ == "__main__":
    asyncio.run(main())
