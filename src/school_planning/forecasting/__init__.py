"""school_planning.forecasting - Forecasting feasibility, baseline heuristics, and backtesting package."""

from school_planning.forecasting.backtesting import (
    DEFAULT_CANDIDATE_MODELS,
    DEFAULT_FOLDS,
    aggregate_state_time_series,
    run_walk_forward_backtest,
)
from school_planning.forecasting.baselines import (
    predict_drift,
    predict_moving_average,
    predict_naive,
)
from school_planning.forecasting.metrics import (
    calculate_mae,
    calculate_mape,
    calculate_rmse,
    calculate_wape,
    evaluate_forecast_metrics,
)
from school_planning.forecasting.models import (
    MODEL_REGISTRY,
    REJECTED_MODELS,
    BaseForecaster,
    DriftForecaster,
    MovingAverageForecaster,
    NaiveForecaster,
    get_forecaster,
)
from school_planning.forecasting.scenarios import (
    DEFAULT_SCENARIO_BANDS,
    estimate_implied_staffing_demand,
    generate_projection_scenarios,
)

__all__ = [
    "DEFAULT_CANDIDATE_MODELS",
    "DEFAULT_FOLDS",
    "DEFAULT_SCENARIO_BANDS",
    "MODEL_REGISTRY",
    "REJECTED_MODELS",
    "BaseForecaster",
    "DriftForecaster",
    "MovingAverageForecaster",
    "NaiveForecaster",
    "aggregate_state_time_series",
    "calculate_mae",
    "calculate_mape",
    "calculate_rmse",
    "calculate_wape",
    "estimate_implied_staffing_demand",
    "evaluate_forecast_metrics",
    "generate_projection_scenarios",
    "get_forecaster",
    "predict_drift",
    "predict_moving_average",
    "predict_naive",
    "run_walk_forward_backtest",
]
