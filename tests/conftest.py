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
