"""baselines.py - Baseline forecasting heuristic implementations.

Implements candidate baseline models defined in config/forecasting.yaml:
  1. Naive Persistence (Random Walk): y_hat_{t+h} = y_t
  2. Linear Drift Model: y_hat_{t+h} = y_t + ((y_t - y_1) / (t - 1))
  3. 3-Year Moving Average: y_hat_{t+1} = mean(y_{t-2}, y_{t-1}, y_t)

Features explicit time index handling to prevent time gaps and non-consecutive
observations from being compressed or treated as adjacent annual steps.
"""

from collections.abc import Sequence

import numpy as np
import pandas as pd


def school_year_to_start_year(year_str: str) -> int:
    """Extract integer starting calendar year from canonical 'YYYY-YY' string.

    Examples:
        '2018-19' -> 2018
        '2022-23' -> 2022
    """
    clean_str = str(year_str).strip()
    prefix = clean_str.split("-")[0]
    try:
        return int(prefix)
    except ValueError as err:
        raise ValueError(
            f"Invalid school year format: '{year_str}'. Expected 'YYYY-YY' format (e.g. '2018-19')."
        ) from err


def _clean_series_and_years(
    history: Sequence[float] | pd.Series | np.ndarray,
    years: Sequence[str] | None = None,
) -> tuple[np.ndarray, list[int] | None]:
    """Validate and align history and optional temporal index, dropping pairwise NaNs."""
    arr = np.asarray(history, dtype=float)

    if years is not None:
        if len(years) != len(arr):
            raise ValueError(
                f"Length mismatch: history has {len(arr)} values but years has {len(years)} entries."
            )
        year_ints = [school_year_to_start_year(y) for y in years]
    else:
        year_ints = None

    valid_mask = ~np.isnan(arr)
    valid_vals = arr[valid_mask]

    if len(valid_vals) == 0:
        raise ValueError("Cannot generate forecast from empty or all-null historical series.")

    if year_ints is not None:
        valid_years = [y for y, m in zip(year_ints, valid_mask, strict=False) if m]
        # Verify chronological ordering
        for i in range(1, len(valid_years)):
            if valid_years[i] <= valid_years[i - 1]:
                raise ValueError(
                    f"Years must be strictly ascending chronologically, got {valid_years[i - 1]} followed by {valid_years[i]}."
                )
        return valid_vals, valid_years

    return valid_vals, None


def predict_naive(
    history: Sequence[float] | pd.Series | np.ndarray,
    years: Sequence[str] | None = None,
    target_year: str | None = None,
    horizon: int = 1,
    clip_non_negative: bool = True,
) -> float | np.ndarray:
    """Generate Naive Persistence forecast (Random Walk benchmark).

    Projects the most recently observed value forward unchanged:
        y_hat_{t+h} = y_t

    Args:
        history: Historical time series ordered chronologically.
        years: Optional sequence of school year strings matching history.
        target_year: Optional target school year string (e.g. '2023-24').
        horizon: Forecast horizon steps forward (default: 1).
        clip_non_negative: Whether to clamp negative values to 0.0.

    Returns:
        Predicted value (scalar if horizon==1, else 1D array).
    """
    series, year_ints = _clean_series_and_years(history, years)
    val = series[-1]
    if clip_non_negative and val < 0.0:
        val = 0.0

    if target_year is not None and year_ints is not None:
        target_int = school_year_to_start_year(target_year)
        gap = target_int - year_ints[-1]
        if gap <= 0:
            raise ValueError(
                f"Target year '{target_year}' ({target_int}) must be after latest historical year ({year_ints[-1]})."
            )
        return float(val)

    if horizon < 1:
        raise ValueError(f"Forecast horizon must be >= 1, got {horizon}")

    if horizon == 1:
        return float(val)
    return np.full(horizon, float(val), dtype=float)


def predict_drift(
    history: Sequence[float] | pd.Series | np.ndarray,
    years: Sequence[str] | None = None,
    target_year: str | None = None,
    horizon: int = 1,
    clip_non_negative: bool = True,
) -> float | np.ndarray:
    """Generate Linear Drift forecast with explicit time-gap accounting.

    Annualized drift rate:
        drift_rate = (y_last - y_first) / (year_last - year_first)
    Prediction:
        y_hat_{target} = y_last + (year_target - year_last) * drift_rate

    Accounts explicitly for calendar time span so missing interior years
    do not distort annual drift rates.

    Args:
        history: Historical time series ordered chronologically.
        years: Optional sequence of school year strings matching history.
        target_year: Optional target school year string (e.g. '2023-24').
        horizon: Forecast horizon (default: 1 step ahead).
        clip_non_negative: Whether to clamp negative values to 0.0.

    Returns:
        Predicted value (scalar if horizon==1, else 1D array).
    """
    series, year_ints = _clean_series_and_years(history, years)
    last_val = series[-1]

    if year_ints is not None:
        time_span = year_ints[-1] - year_ints[0]
        if time_span < 1:
            drift = 0.0
        else:
            drift = (last_val - series[0]) / float(time_span)

        if target_year is not None:
            target_int = school_year_to_start_year(target_year)
            h_years = target_int - year_ints[-1]
            if h_years <= 0:
                raise ValueError(
                    f"Target year '{target_year}' ({target_int}) must be after latest historical year ({year_ints[-1]})."
                )
            pred = last_val + h_years * drift
            if clip_non_negative and pred < 0.0:
                pred = 0.0
            return float(pred)
    else:
        t = len(series)
        drift = (last_val - series[0]) / float(t - 1) if t >= 2 else 0.0

    if horizon < 1:
        raise ValueError(f"Forecast horizon must be >= 1, got {horizon}")

    steps = np.arange(1, horizon + 1)
    preds = last_val + steps * drift

    if clip_non_negative:
        preds = np.clip(preds, 0.0, None)

    if horizon == 1:
        return float(preds[0])
    return preds.astype(float)


def predict_moving_average(
    history: Sequence[float] | pd.Series | np.ndarray,
    years: Sequence[str] | None = None,
    target_year: str | None = None,
    window: int = 3,
    horizon: int = 1,
    clip_non_negative: bool = True,
) -> float | np.ndarray:
    """Generate Moving Average forecast adhering to consecutive year chains.

    Computes the arithmetic mean over the latest consecutive observations
    ending at the latest observed period. If there is a calendar time gap,
    older observations prior to the gap are NOT averaged into the heuristic.

    Args:
        history: Historical time series ordered chronologically.
        years: Optional sequence of school year strings matching history.
        target_year: Optional target school year string (e.g. '2023-24').
        window: Moving average window size (default: 3 years).
        horizon: Forecast horizon (default: 1 step ahead).
        clip_non_negative: Whether to clamp negative values to 0.0.

    Returns:
        Predicted value (scalar if horizon==1 or target_year given, else 1D array).
    """
    if horizon < 1:
        raise ValueError(f"Forecast horizon must be >= 1, got {horizon}")
    if window < 1:
        raise ValueError(f"Moving average window must be >= 1, got {window}")

    series, year_ints = _clean_series_and_years(history, years)

    if year_ints is not None:
        if target_year is not None:
            target_int = school_year_to_start_year(target_year)
            gap = target_int - year_ints[-1]
            if gap <= 0:
                raise ValueError(
                    f"Target year '{target_year}' ({target_int}) must be after latest historical year ({year_ints[-1]})."
                )

        # Find contiguous consecutive observations ending at year_ints[-1]
        consecutive_vals = [series[-1]]
        current_year = year_ints[-1]

        for i in range(len(year_ints) - 2, -1, -1):
            if year_ints[i] == current_year - 1:
                consecutive_vals.append(series[i])
                current_year = year_ints[i]
                if len(consecutive_vals) == window:
                    break
            else:
                # Time gap detected; stop collecting earlier observations
                break

        val = float(np.mean(consecutive_vals))
    else:
        subset = series[-window:]
        val = float(np.mean(subset))

    if clip_non_negative and val < 0.0:
        val = 0.0

    if horizon == 1 or target_year is not None:
        return float(val)
    return np.full(horizon, float(val), dtype=float)
