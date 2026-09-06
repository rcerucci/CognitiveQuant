"""Backtest motor-only module (F6).

Carrega e executa backtest histórico usando motor F1-F5 in-memory.
Sem TA, sem MCP, sem executor.

Spec F6 §10.1
"""

# Fixed instruments from spec §9.2
F6_INSTRUMENTS = [
    "EUR/USD",
    "GBP/JPY",
    "USD/CAD",
    "AUD/NZD",
    "US500",
    "GER30",
    "JP225",
    "XAU/USD",
    "USOIL",
    "NAS100",
]

# F6 trigger thresholds (from spec)
F6_FORCE_THRESHOLD = 0.60  # ALTA or MEDIA confianca

# Timeframe
F6_TIMEFRAME = "M30"

# Sharpe calculation parameters
SHARPE_RISK_FREE_RATE = 0.0
SHARPE_DAILY_ANNUALIZATION = 252  # sqrt(252)

# Gate criteria
SHARPE_GATE_THRESHOLD = 0.5
SHARPE_GATE_MIN_INSTRUMENTS = 7  # >= 7/10

# Metric targets from spec §10.1
TARGET_SHARPE = 0.5
TARGET_WR = 0.45
TARGET_PF = 1.3
TARGET_MAXDD = 0.15
TARGET_TRIGGER_RATE_MIN = 0.05
TARGET_TRIGGER_RATE_MAX = 0.15
TARGET_TAU_MEDIAN_MIN = 3
TARGET_TAU_MEDIAN_MAX = 8

# Public API exports
from motor.backtest.loader import (
    BacktestLoader,
    LoaderResult,
    LoaderStatus,
    InstrumentBars,
    load_historical_data,
    load_fixture_data,
)

from motor.backtest.runner import (
    BarRunner,
    BacktestResult,
    RunResult,
    RunnerStatus,
    run_backtest,
)

from motor.backtest.pnl import (
    PnLCalculator,
    PnLResult,
    Trade,
    Position,
    TradeStatus,
    calculate_pnl,
    run_pnl_simulation,
)

from motor.backtest.metrics import (
    InstrumentMetrics,
    GateResult,
    MetricsCalculator,
    check_gate,
    calculate_sharpe_from_equity,
)

from motor.backtest.report import (
    BacktestReport,
    InstrumentReport,
    ReportBuilder,
    Veredito,
    build_backtest_report,
)

from motor.backtest.pipeline import (
    F6Pipeline,
    PipelineResult,
    PipelineOutput,
    PipelineStatus,
    run_f6_pipeline,
)

__all__ = [
    # Constants
    "F6_INSTRUMENTS",
    "F6_FORCE_THRESHOLD",
    "F6_TIMEFRAME",
    "SHARPE_RISK_FREE_RATE",
    "SHARPE_DAILY_ANNUALIZATION",
    "SHARPE_GATE_THRESHOLD",
    "SHARPE_GATE_MIN_INSTRUMENTS",
    "TARGET_SHARPE",
    "TARGET_WR",
    "TARGET_PF",
    "TARGET_MAXDD",
    "TARGET_TRIGGER_RATE_MIN",
    "TARGET_TRIGGER_RATE_MAX",
    "TARGET_TAU_MEDIAN_MIN",
    "TARGET_TAU_MEDIAN_MAX",
    # Loader
    "BacktestLoader",
    "LoaderResult",
    "LoaderStatus",
    "InstrumentBars",
    "load_historical_data",
    "load_fixture_data",
    # Runner
    "BarRunner",
    "BacktestResult",
    "RunResult",
    "RunnerStatus",
    "run_backtest",
    # PnL
    "PnLCalculator",
    "PnLResult",
    "Trade",
    "Position",
    "TradeStatus",
    "calculate_pnl",
    "run_pnl_simulation",
    # Metrics
    "InstrumentMetrics",
    "GateResult",
    "MetricsCalculator",
    "check_gate",
    "calculate_sharpe_from_equity",
    # Report
    "BacktestReport",
    "InstrumentReport",
    "ReportBuilder",
    "Veredito",
    "build_backtest_report",
    # Pipeline
    "F6Pipeline",
    "PipelineResult",
    "PipelineOutput",
    "PipelineStatus",
    "run_f6_pipeline",
]