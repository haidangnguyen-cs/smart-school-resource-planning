"""models.py - Forecasting model abstractions and registry.

Defines unified candidate forecasting models and records rejected models
in accordance with config/forecasting.yaml:
  - Naive Persistence (Random Walk)
  - Linear Drift Model
  - 3-Year Moving Average

Features explicit time index support to prevent temporal gap compression.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from school_planning.forecasting.baselines import (
    predict_drift,
    predict_moving_average,
    predict_naive,
)

# Documented rejected models and reasons per config/forecasting.yaml
REJECTED_MODELS: dict[str, str] = {
    "high_order_arima": (
        "Requires minimum 30-50 time periods for reliable parameter identification "
        "and seasonal differencing."
    ),
    "prophet": (
        "Requires multi-year daily/weekly/monthly seasonality; invalid and severely "
        "over-parameterized for 5 annual steps."
    ),
    "machine_learning_deep_learning": (
        "Extreme risk of spurious correlation, over-parameterization, and memorization on T=5."
    ),
}


class BaseForecaster(ABC):
    """Abstract base class for annual aggregate forecasters."""

    def __init__(self, name: str, clip_non_negative: bool = True) -> None:
        self.name = name
        self.clip_non_negative = clip_non_negative
        self._history: np.ndarray | None = None
        self._years: list[str] | None = None

    @abstractmethod
    def fit(
        self,
        history: Sequence[float] | pd.Series | np.ndarray,
        years: Sequence[str] | None = None,
    ) -> "BaseForecaster":
        """Fit model on historical observations with optional time index."""

    @abstractmethod
    def predict(
        self,
        horizon: int = 1,
        target_year: str | None = None,
    ) -> float | np.ndarray:
        """Generate forecast for specified horizon or target school year."""

    @property
    def history(self) -> np.ndarray:
        """Return fitted historical data."""
        if self._history is None:
            raise RuntimeError("Model has not been fitted. Call fit() before accessing history.")
        return self._history

    @property
    def years(self) -> list[str] | None:
        """Return fitted chronological school years."""
        return self._years


class NaiveForecaster(BaseForecaster):
    """Naive Persistence (Random Walk) benchmark model: y_hat_{t+h} = y_t."""

    def __init__(self, clip_non_negative: bool = True) -> None:
        super().__init__(name="naive_persistence", clip_non_negative=clip_non_negative)

    def fit(
        self,
        history: Sequence[float] | pd.Series | np.ndarray,
        years: Sequence[str] | None = None,
    ) -> "NaiveForecaster":
        arr = np.asarray(history, dtype=float)
        valid_mask = ~np.isnan(arr)
        valid = arr[valid_mask]
        if len(valid) == 0:
            raise ValueError("Cannot fit NaiveForecaster on empty or all-null history.")
        self._history = valid
        if years is not None:
            self._years = [y for y, m in zip(years, valid_mask, strict=False) if m]
        else:
            self._years = None
        return self

    def predict(
        self,
        horizon: int = 1,
        target_year: str | None = None,
    ) -> float | np.ndarray:
        if self._history is None:
            raise RuntimeError("Model must be fitted before calling predict().")
        return predict_naive(
            self._history,
            years=self._years,
            target_year=target_year,
            horizon=horizon,
            clip_non_negative=self.clip_non_negative,
        )


class DriftForecaster(BaseForecaster):
    """Linear Drift model: y_hat_{t+h} = y_t + h * ((y_t - y_1) / (year_t - year_1))."""

    def __init__(self, clip_non_negative: bool = True) -> None:
        super().__init__(name="drift", clip_non_negative=clip_non_negative)

    def fit(
        self,
        history: Sequence[float] | pd.Series | np.ndarray,
        years: Sequence[str] | None = None,
    ) -> "DriftForecaster":
        arr = np.asarray(history, dtype=float)
        valid_mask = ~np.isnan(arr)
        valid = arr[valid_mask]
        if len(valid) == 0:
            raise ValueError("Cannot fit DriftForecaster on empty or all-null history.")
        self._history = valid
        if years is not None:
            self._years = [y for y, m in zip(years, valid_mask, strict=False) if m]
        else:
            self._years = None
        return self

    def predict(
        self,
        horizon: int = 1,
        target_year: str | None = None,
    ) -> float | np.ndarray:
        if self._history is None:
            raise RuntimeError("Model must be fitted before calling predict().")
        return predict_drift(
            self._history,
            years=self._years,
            target_year=target_year,
            horizon=horizon,
            clip_non_negative=self.clip_non_negative,
        )


class MovingAverageForecaster(BaseForecaster):
    """Moving Average heuristic model with consecutive calendar year checking."""

    def __init__(self, window: int = 3, clip_non_negative: bool = True) -> None:
        super().__init__(name=f"moving_average_{window}yr", clip_non_negative=clip_non_negative)
        self.window = window

    def fit(
        self,
        history: Sequence[float] | pd.Series | np.ndarray,
        years: Sequence[str] | None = None,
    ) -> "MovingAverageForecaster":
        arr = np.asarray(history, dtype=float)
        valid_mask = ~np.isnan(arr)
        valid = arr[valid_mask]
        if len(valid) == 0:
            raise ValueError("Cannot fit MovingAverageForecaster on empty or all-null history.")
        self._history = valid
        if years is not None:
            self._years = [y for y, m in zip(years, valid_mask, strict=False) if m]
        else:
            self._years = None
        return self

    def predict(
        self,
        horizon: int = 1,
        target_year: str | None = None,
    ) -> float | np.ndarray:
        if self._history is None:
            raise RuntimeError("Model must be fitted before calling predict().")
        return predict_moving_average(
            self._history,
            years=self._years,
            target_year=target_year,
            window=self.window,
            horizon=horizon,
            clip_non_negative=self.clip_non_negative,
        )


MODEL_REGISTRY: dict[str, type[BaseForecaster]] = {
    "naive_persistence": NaiveForecaster,
    "drift": DriftForecaster,
    "moving_average_3yr": MovingAverageForecaster,
}


def get_forecaster(model_name: str, **kwargs: Any) -> BaseForecaster:
    """Instantiate a forecaster by canonical name.

    Args:
        model_name: One of 'naive_persistence', 'drift', 'moving_average_3yr'.
        **kwargs: Model constructor arguments.

    Returns:
        Configured BaseForecaster instance.
    """
    if model_name not in MODEL_REGISTRY:
        valid_names = list(MODEL_REGISTRY.keys())
        raise ValueError(f"Unknown model_name '{model_name}'. Choose from: {valid_names}")
    return MODEL_REGISTRY[model_name](**kwargs)
