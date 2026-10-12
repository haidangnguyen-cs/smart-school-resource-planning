"""Pytest configuration and shared fixtures for smart-school-resource-planning."""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def config_dir() -> Path:
    """Return the absolute path to the config directory."""
    return CONFIG_DIR


@pytest.fixture(scope="session")
def load_yaml():
    """Helper function fixture to load and parse YAML files."""

    def _loader(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    return _loader


@pytest.fixture(scope="session")
def project_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "project.yaml")


@pytest.fixture(scope="session")
def sources_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "sources.yaml")


@pytest.fixture(scope="session")
def column_mapping_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "column_mapping.yaml")


@pytest.fixture(scope="session")
def quality_rules_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "quality_rules.yaml")


@pytest.fixture(scope="session")
def kpi_definitions_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "kpi_definitions.yaml")


@pytest.fixture(scope="session")
def forecasting_config(config_dir, load_yaml) -> dict:
    return load_yaml(config_dir / "forecasting.yaml")


@pytest.fixture
def synthetic_panel_df():
    """Create synthetic longitudinal panel for testing table and chart formatting."""
    import pandas as pd

    records = []
    years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
    levels = ["Primary", "Middle", "High", "Other"]
    states = [("06", "California"), ("48", "Texas"), ("36", "New York")]

    for yr_idx, yr in enumerate(years):
        for s_idx in range(40):
            state_fips, state_name = states[s_idx % len(states)]
            lvl = levels[s_idx % len(levels)]
            students = 300.0 + (s_idx * 15.0) + (yr_idx * 5.0)
            teachers = 20.0 + (s_idx * 0.8) + (yr_idx * 0.2)
            ratio = students / teachers
            tier = (s_idx % 6) + 1

            records.append(
                {
                    "school_id": f"SCH_{s_idx:04d}",
                    "school_year": yr,
                    "state_fips": state_fips,
                    "state_name": state_name,
                    "school_level": lvl,
                    "is_operational": True,
                    "is_charter": (s_idx % 5 == 0),
                    "total_students": students,
                    "teacher_fte": teachers,
                    "student_teacher_ratio": ratio,
                    "resource_pressure_priority": tier,
                    "priority_tier": tier,
                }
            )

    return pd.DataFrame(records)


@pytest.fixture
def synthetic_backtest_df():
    """Create synthetic backtesting summary DataFrame."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "fold_id": "fold_1",
                "test_year": "2021-22",
                "target_col": "total_students",
                "model_name": "naive_persistence",
                "n_observations": 55,
                "wape": 1.10,
                "mae": 9916.0,
                "rmse": 18616.0,
                "min_coverage_pct": 91.2,
                "median_coverage_pct": 99.9,
            },
            {
                "fold_id": "fold_1",
                "test_year": "2021-22",
                "target_col": "total_students",
                "model_name": "drift",
                "n_observations": 55,
                "wape": 1.82,
                "mae": 16323.0,
                "rmse": 36226.0,
                "min_coverage_pct": 91.2,
                "median_coverage_pct": 99.9,
            },
            {
                "fold_id": "fold_2",
                "test_year": "2022-23",
                "target_col": "total_students",
                "model_name": "naive_persistence",
                "n_observations": 55,
                "wape": 0.93,
                "mae": 8406.0,
                "rmse": 16783.0,
                "min_coverage_pct": 87.7,
                "median_coverage_pct": 100.0,
            },
        ]
    )


@pytest.fixture
def synthetic_projections_df():
    """Create synthetic scenario projections DataFrame."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "state_fips": "06",
                "state_name": "California",
                "latest_historical_value": 5500000.0,
                "baseline_projection": 5480000.0,
                "scenario_low_contraction_minus_2pct": 5370400.0,
                "scenario_high_expansion_plus_2pct": 5589600.0,
                "latest_historical_teacher_fte": 280000.0,
                "implied_teacher_fte_constant_ratio": 278981.8,
                "implied_teacher_fte_policy_target": 365333.3,
                "is_latest_year_valid": True,
            },
            {
                "state_fips": "48",
                "state_name": "Texas",
                "latest_historical_value": 5200000.0,
                "baseline_projection": 5250000.0,
                "scenario_low_contraction_minus_2pct": 5145000.0,
                "scenario_high_expansion_plus_2pct": 5355000.0,
                "latest_historical_teacher_fte": 350000.0,
                "implied_teacher_fte_constant_ratio": 353365.4,
                "implied_teacher_fte_policy_target": 350000.0,
                "is_latest_year_valid": True,
            },
        ]
    )
