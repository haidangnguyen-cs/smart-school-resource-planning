"""metrics.py - Forecast error evaluation metrics for school resource forecasting.

Implements standard forecasting evaluation metrics per config/forecasting.yaml:
  - MAE (Mean Absolute Error)
  - WAPE (Weighted Absolute Percentage Error - preferred metric)
  - MAPE (Mean Absolute Percentage Error)
  - RMSE (Root Mean Squared Error)
"""

import numpy as np
import pandas as pd


def _validate_and_align(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Validate and align actual and predicted series, dropping pairwise NaNs."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)

    if yt.shape != yp.shape:
        raise ValueError(f"Shape mismatch: y_true shape {yt.shape} != y_pred shape {yp.shape}")

    if len(yt) == 0:
        raise ValueError("Cannot calculate metrics on empty input series.")

    valid_mask = (~np.isnan(yt)) & (~np.isnan(yp))
    if not np.any(valid_mask):
        raise ValueError("No valid overlapping non-null observations between actual and predicted.")

    return yt[valid_mask], yp[valid_mask]


def calculate_mae(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> float:
    """Calculate Mean Absolute Error (MAE): mean(|y - y_hat|).

    Returns:
        MAE in native units.
    """
    yt, yp = _validate_and_align(y_true, y_pred)
    return float(np.mean(np.abs(yt - yp)))


def calculate_wape(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> float:
    """Calculate Weighted Absolute Percentage Error (WAPE): sum(|y - y_hat|) / sum(y) * 100.

    This is the primary aggregate evaluation metric specified in config/forecasting.yaml
    because it avoids denominator distortion from small individual actual values.

    Returns:
        WAPE as a percentage (e.g., 2.5 for 2.5%).
    """
    yt, yp = _validate_and_align(y_true, y_pred)
    denom = float(np.sum(yt))
    if denom == 0.0:
        return float(np.nan)
    return float(np.sum(np.abs(yt - yp)) / denom * 100.0)


def calculate_mape(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> float:
    """Calculate Mean Absolute Percentage Error (MAPE): mean(|y - y_hat| / y) * 100.

    Excludes observations where actual y == 0 to avoid division by zero.

    Returns:
        MAPE as a percentage.
    """
    yt, yp = _validate_and_align(y_true, y_pred)
    non_zero = yt != 0.0
    if not np.any(non_zero):
        return float(np.nan)
    return float(np.mean(np.abs((yt[non_zero] - yp[non_zero]) / yt[non_zero])) * 100.0)


def calculate_rmse(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> float:
    """Calculate Root Mean Squared Error (RMSE): sqrt(mean((y - y_hat)^2)).

    Returns:
        RMSE in native units.
    """
    yt, yp = _validate_and_align(y_true, y_pred)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def evaluate_forecast_metrics(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> dict[str, float]:
    """Compute comprehensive forecast evaluation metrics dict.

    Returns:
        Dictionary containing 'mae', 'wape', 'mape', and 'rmse'.
    """
    return {
        "mae": calculate_mae(y_true, y_pred),
        "wape": calculate_wape(y_true, y_pred),
        "mape": calculate_mape(y_true, y_pred),
        "rmse": calculate_rmse(y_true, y_pred),
    }
