"""test_end_to_end_pipeline.py - Integration tests for the full pipeline and output invariants.

Validates:
1. Pipeline orchestrator execution logic and stage handling.
2. In-memory synthetic end-to-end transformation, KPI, triage, and forecasting flow.
3. Processed dataset schema invariants, key uniqueness, and data traceability.
4. Output tables, figures, and deliverable document integrity.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

from school_planning.analytics.kpis import calculate_school_kpis
from school_planning.analytics.resource_pressure import (
    classify_resource_pressure,
    summarize_resource_pressure_tiers,
)
from school_planning.forecasting.scenarios import generate_projection_scenarios
from school_planning.pipeline.run_pipeline import PIPELINE_STAGES, run_pipeline
from school_planning.reporting.generate_report import generate_all_deliverables
from school_planning.reporting.tables import (
    format_kpi_summary_table,
    format_resource_pressure_tier_table,
    format_state_summary_table,
)


class TestPipelineOrchestrator:
    """Test the central pipeline runner and stage orchestrator."""

    def test_pipeline_stages_definition(self):
        """Verify that all 6 expected stages are defined with valid paths."""
        assert len(PIPELINE_STAGES) == 6
        stage_ids = [s["stage_id"] for s in PIPELINE_STAGES]
        assert stage_ids == [1, 2, 3, 4, 5, 6]

        root = Path.cwd()
        for s in PIPELINE_STAGES:
            script_file = root / s["script"]
            assert script_file.exists(), f"Pipeline stage script missing: {s['script']}"

    def test_run_pipeline_missing_script(self, tmp_path):
        """Verify runner fails gracefully when a stage script does not exist."""
        # Point to an empty directory where scripts don't exist
        res = run_pipeline(start_stage=1, end_stage=1, base_dir=tmp_path)
        assert res["success"] is False
        assert res["failed_stage"] == 1
        assert "not found" in res["stages"][0]["error"].lower()

    def test_run_pipeline_orchestration_isolated(self, tmp_path, monkeypatch):
        """Verify pipeline orchestrator handles multi-stage execution and success reporting deterministically."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        dummy_script = scripts_dir / "dummy_stage.py"
        dummy_script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

        mock_stages = [
            {
                "stage_id": 1,
                "name": "Mock Stage 1",
                "script": "scripts/dummy_stage.py",
                "description": "Deterministic mock stage 1",
            },
            {
                "stage_id": 2,
                "name": "Mock Stage 2",
                "script": "scripts/dummy_stage.py",
                "description": "Deterministic mock stage 2",
            },
        ]
        pipeline_module = sys.modules["school_planning.pipeline.run_pipeline"]
        monkeypatch.setattr(pipeline_module, "PIPELINE_STAGES", mock_stages)

        res = run_pipeline(start_stage=1, end_stage=2, base_dir=tmp_path)
        assert res["success"] is True
        assert res["failed_stage"] is None
        assert len(res["stages"]) == 2
        assert res["stages"][0]["status"] == "SUCCESS"
        assert res["stages"][1]["status"] == "SUCCESS"
        assert res["stages"][0]["returncode"] == 0
        assert res["stages"][1]["returncode"] == 0
        assert res["total_elapsed_seconds"] >= 0

    def test_run_pipeline_single_stage_deliverables_smoke(self):
        """Execute Stage 6 (generate deliverables) via runner when processed panel exists."""
        root = Path.cwd()
        aug_path = root / "data" / "processed" / "school_year_panel_augmented.parquet"
        base_path = root / "data" / "processed" / "school_year_panel.parquet"
        panel_path = aug_path if aug_path.exists() else base_path

        if not panel_path.exists():
            pytest.skip(
                f"Required processed panel not found at {panel_path}. "
                "Skipping Stage 6 smoke test in clean checkout without data."
            )

        res = run_pipeline(start_stage=6, end_stage=6)
        assert res["success"] is True, f"Stage 6 execution failed: {res.get('stages')}"
        assert res["failed_stage"] is None
        assert len(res["stages"]) == 1
        assert res["stages"][0]["stage_id"] == 6
        assert res["stages"][0]["status"] == "SUCCESS"
        assert res["stages"][0]["elapsed_seconds"] > 0


class TestSyntheticEndToEndDataFlow:
    """Validate data flow through cleaning, KPIs, triage, forecasting, and reporting on synthetic data."""

    def test_synthetic_end_to_end_flow(self, synthetic_panel_df, tmp_path):
        """Run complete synthetic analytical workflow from panel to report deliverables."""
        # 1. KPI calculations
        kpi_df = calculate_school_kpis(synthetic_panel_df)
        assert "student_teacher_ratio" in kpi_df.columns
        assert not kpi_df["student_teacher_ratio"].isna().all()

        # 2. Resource pressure classification
        classified_df = classify_resource_pressure(synthetic_panel_df)
        assert "resource_pressure_priority" in classified_df.columns
        assert set(classified_df["resource_pressure_priority"].unique()).issubset(
            {1, 2, 3, 4, 5, 6}
        )

        # 3. Tier summaries
        tier_summary = summarize_resource_pressure_tiers(
            classified_df[classified_df["school_year"] == "2022-23"]
        )
        assert len(tier_summary) == 6
        assert (
            tier_summary["operational_observation_count"].sum() == 40
        )  # 40 operational schools in fixture

        # 4. State-level forecasting scenarios
        state_aggs = (
            synthetic_panel_df.groupby(["state_fips", "state_name", "school_year"])
            .agg(total_students=("total_students", "sum"), teacher_fte=("teacher_fte", "sum"))
            .reset_index()
        )
        proj_scenarios = generate_projection_scenarios(
            state_aggs,
            target_col="total_students",
            entity_col="state_fips",
            display_col="state_name",
            year_col="school_year",
        )
        assert not proj_scenarios.empty
        assert "baseline_projection" in proj_scenarios.columns

        # 5. Reporting tables
        kpi_table = format_kpi_summary_table(synthetic_panel_df)
        assert len(kpi_table) == 5
        state_table = format_state_summary_table(classified_df, school_year="2022-23")
        assert len(state_table) == 3  # CA, NY, TX
        tier_table = format_resource_pressure_tier_table(classified_df, school_year="2022-23")
        assert len(tier_table) == 6

        # 6. Deliverable document generation
        dummy_backtest = pd.DataFrame(
            [
                {
                    "model_name": "naive",
                    "wape": 0.02,
                    "mae": 1500.0,
                    "rmse": 2000.0,
                    "horizon": 1,
                }
            ]
        )
        dummy_proj = pd.DataFrame(
            [
                {
                    "state_fips": "06",
                    "state_name": "California",
                    "baseline_2022_23": 50000.0,
                    "baseline_projection": 50500.0,
                    "scenario_contraction": 49490.0,
                    "scenario_expansion": 51510.0,
                    "implied_teacher_demand_baseline": 2525.0,
                    "is_latest_year_valid": True,
                }
            ]
        )
        deliverables = generate_all_deliverables(
            panel_df=classified_df,
            state_summary_df=state_table,
            backtest_df=dummy_backtest,
            projections_df=dummy_proj,
            output_dir=tmp_path,
        )
        for p in deliverables.values():
            assert p.exists()
            assert p.stat().st_size > 100


class TestProcessedOutputsAndArtifactInvariants:
    """Verify invariants on real processed outputs when available on disk."""

    @pytest.fixture(autouse=True)
    def setup_paths(self):
        self.root = Path.cwd()
        aug_path = self.root / "data" / "processed" / "school_year_panel_augmented.parquet"
        base_path = self.root / "data" / "processed" / "school_year_panel.parquet"
        self.panel_path = aug_path if aug_path.exists() else base_path
        self.tables_dir = self.root / "outputs" / "tables"
        self.figures_dir = self.root / "outputs" / "figures"
        self.deliverables_dir = self.root / "deliverables"

    def test_processed_panel_invariants(self):
        """Verify grain, uniqueness, and boundary invariants on processed panel if present."""
        if not self.panel_path.exists():
            pytest.skip("Processed panel not present in test environment.")

        df = pd.read_parquet(self.panel_path)
        # Check grain: school_id + school_year must be unique
        dups = df.duplicated(subset=["school_id", "school_year"]).sum()
        assert dups == 0, f"Found {dups} duplicate composite primary keys in panel."

        # Check school years: strictly the 5 expected CCD years
        years = sorted(df["school_year"].unique())
        expected_years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        assert years == expected_years

        # Check non-negative constraints where observed
        valid_students = df["total_students"].dropna()
        assert (valid_students >= 0).all()

        valid_teachers = df["teacher_fte"].dropna()
        assert (valid_teachers >= 0).all()

        # Check ratio validity: where teacher_fte == 0, ratio must be null or infinite
        zero_teacher = df[df["teacher_fte"] == 0]
        if not zero_teacher.empty and "student_teacher_ratio" in df.columns:
            # Ratios for 0 teacher FTE must be NaN
            assert zero_teacher["student_teacher_ratio"].isna().all()

        # Check priority tier values: 1-6
        if "resource_pressure_priority" in df.columns:
            priorities = df["resource_pressure_priority"].dropna().unique()
            assert set(priorities).issubset({1, 2, 3, 4, 5, 6})

    REQUIRED_TABLES = (
        "state_annual_aggregates.csv",
        "resource_pressure_triage_queue_p1.csv",
        "resource_pressure_triage_queue_p2.csv",
        "backtest_model_comparison.csv",
        "retrospective_2023_24_projections.csv",
    )
    REQUIRED_FIGS = (
        "longitudinal_trends.png",
        "ratio_distribution.png",
        "resource_pressure_tiers.png",
        "backtest_model_comparison.png",
        "retrospective_scenario_projections.png",
    )
    REQUIRED_DELIVERABLES = (
        "executive_summary.md",
        "technical_report.md",
        "recommendations.md",
        "presentation_outline.md",
    )

    @classmethod
    def verify_tables_set(
        cls, tables_dir: Path, required_tables: list[str] | tuple[str, ...] | None = None
    ) -> None:
        """Verify that required output tables exist and contain valid non-empty data.

        Skips only when the entire table artifact set is absent (clean checkout).
        Fails if any required table is missing when others are present.
        """
        targets = required_tables or cls.REQUIRED_TABLES
        existing = [t for t in targets if (tables_dir / t).exists()]
        if not existing:
            pytest.skip(f"Output tables not present in {tables_dir}.")

        missing = [t for t in targets if not (tables_dir / t).exists()]
        assert not missing, f"Incomplete output tables generated; missing: {missing}"

        for tbl_name in targets:
            tbl_path = tables_dir / tbl_name
            df = pd.read_csv(tbl_path)
            assert len(df) > 0, f"Output table {tbl_name} is empty."
            assert len(df.columns) > 1, f"Output table {tbl_name} has invalid column count."

    @classmethod
    def verify_figures_set(
        cls, figures_dir: Path, required_figs: list[str] | tuple[str, ...] | None = None
    ) -> None:
        """Verify that required publication figures exist and are non-empty.

        Skips only when the entire figure artifact set is absent (clean checkout).
        Fails if any required figure is missing when others are present.
        """
        targets = required_figs or cls.REQUIRED_FIGS
        existing = [f for f in targets if (figures_dir / f).exists()]
        if not existing:
            pytest.skip(f"Output figures not present in {figures_dir}.")

        missing = [f for f in targets if not (figures_dir / f).exists()]
        assert not missing, f"Incomplete output figures generated; missing: {missing}"

        for fig_name in targets:
            fig_path = figures_dir / fig_name
            assert fig_path.stat().st_size > 5000, f"Figure {fig_name} is suspiciously small."

    @classmethod
    def verify_deliverables_set(
        cls,
        deliverables_dir: Path,
        required_deliverables: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        """Verify that all tracked deliverable documents exist, are non-empty, and contain headings.

        Does not silently skip when individual files are missing.
        """
        targets = required_deliverables or cls.REQUIRED_DELIVERABLES
        missing = [d for d in targets if not (deliverables_dir / d).exists()]
        assert not missing, f"Missing deliverable documents: {missing}"

        for doc_name in targets:
            doc_path = deliverables_dir / doc_name
            assert doc_path.exists(), f"Deliverable {doc_name} is missing."
            content = doc_path.read_text(encoding="utf-8")
            assert len(content) > 500, f"Deliverable {doc_name} is too short."
            assert "# " in content, f"Deliverable {doc_name} lacks H1 heading."

    def test_output_tables_integrity(self):
        """Verify that all required output tables exist and contain valid non-empty data."""
        self.verify_tables_set(self.tables_dir)

    def test_output_figures_exist(self):
        """Verify that all 5 required publication figures exist and are non-empty."""
        self.verify_figures_set(self.figures_dir)

    def test_deliverable_documents_integrity(self):
        """Verify that all 4 markdown deliverables exist, contain headers and substantive text."""
        self.verify_deliverables_set(self.deliverables_dir)


class TestArtifactIntegritySkipSemantics:
    """Validate skip semantics for clean checkouts vs assertion failures for partial generation."""

    def test_tables_fully_absent_triggers_skip(self, tmp_path):
        """Clean checkout with zero generated tables must skip gracefully."""
        empty_dir = tmp_path / "empty_tables"
        empty_dir.mkdir()
        with pytest.raises(pytest.skip.Exception):
            TestProcessedOutputsAndArtifactInvariants.verify_tables_set(empty_dir)

    def test_tables_partially_present_fails_identifying_missing(self, tmp_path):
        """Incomplete table generation must fail and name the missing tables."""
        partial_dir = tmp_path / "partial_tables"
        partial_dir.mkdir()
        sample_csv = partial_dir / "state_annual_aggregates.csv"
        sample_csv.write_text("state_fips,state_name\n01,Alabama\n", encoding="utf-8")

        with pytest.raises(AssertionError) as exc_info:
            TestProcessedOutputsAndArtifactInvariants.verify_tables_set(partial_dir)
        err_msg = str(exc_info.value)
        assert "Incomplete output tables generated; missing:" in err_msg
        assert "resource_pressure_triage_queue_p1.csv" in err_msg
        assert "retrospective_2023_24_projections.csv" in err_msg

    def test_figures_fully_absent_triggers_skip(self, tmp_path):
        """Clean checkout with zero generated figures must skip gracefully."""
        empty_dir = tmp_path / "empty_figures"
        empty_dir.mkdir()
        with pytest.raises(pytest.skip.Exception):
            TestProcessedOutputsAndArtifactInvariants.verify_figures_set(empty_dir)

    def test_figures_partially_present_fails_identifying_missing(self, tmp_path):
        """Incomplete figure generation must fail and name the missing figures."""
        partial_dir = tmp_path / "partial_figures"
        partial_dir.mkdir()
        sample_fig = partial_dir / "longitudinal_trends.png"
        sample_fig.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 6000)

        with pytest.raises(AssertionError) as exc_info:
            TestProcessedOutputsAndArtifactInvariants.verify_figures_set(partial_dir)
        err_msg = str(exc_info.value)
        assert "Incomplete output figures generated; missing:" in err_msg
        assert "ratio_distribution.png" in err_msg
        assert "retrospective_scenario_projections.png" in err_msg

    def test_deliverables_missing_file_fails_and_does_not_skip(self, tmp_path):
        """Missing tracked deliverable must fail assertion and not skip."""
        deliv_dir = tmp_path / "deliverables"
        deliv_dir.mkdir()
        for name in [
            "executive_summary.md",
            "technical_report.md",
            "recommendations.md",
        ]:
            doc = deliv_dir / name
            doc.write_text("# Title\n" + "Body paragraph " * 50, encoding="utf-8")

        with pytest.raises(AssertionError) as exc_info:
            TestProcessedOutputsAndArtifactInvariants.verify_deliverables_set(deliv_dir)
        err_msg = str(exc_info.value)
        assert "Missing deliverable documents:" in err_msg
        assert "presentation_outline.md" in err_msg
