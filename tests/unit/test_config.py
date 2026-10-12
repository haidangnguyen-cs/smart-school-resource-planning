"""Unit tests for configuration schemas, data contracts, and tier logic."""

from pathlib import Path

import pytest


class TestConfigurationFilesExist:
    """Ensure all required configuration files exist on disk."""

    @pytest.mark.parametrize(
        "filename",
        [
            "project.yaml",
            "sources.yaml",
            "column_mapping.yaml",
            "quality_rules.yaml",
            "kpi_definitions.yaml",
            "forecasting.yaml",
        ],
    )
    def test_config_file_exists(self, config_dir: Path, filename: str):
        filepath = config_dir / filename
        assert filepath.exists(), f"Configuration file {filename} does not exist in {config_dir}"
        assert filepath.stat().st_size > 0, f"Configuration file {filename} is empty"


class TestProjectConfigContract:
    """Validate project.yaml schema, composite key, and scoping contracts."""

    def test_project_metadata(self, project_config: dict):
        proj = project_config.get("project", {})
        assert proj.get("name") == "smart-school-resource-planning"
        assert proj.get("version") == "0.1.0"

    def test_time_scope_contract(self, project_config: dict):
        time_scope = project_config.get("time_scope", {})
        assert time_scope.get("num_years") == 5
        assert time_scope.get("start_year") == "2018-19"
        assert time_scope.get("end_year") == "2022-23"
        expected_years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        assert time_scope.get("school_years") == expected_years
        assert time_scope.get("pandemic_anomaly_year") == "2020-21"

    def test_target_panel_composite_primary_key(self, project_config: dict):
        panel = project_config.get("target_panel", {})
        assert panel.get("grain") == ["school_id", "school_year"]
        # Analytical panel requires an explicit composite primary key [school_id, school_year]
        assert panel.get("primary_key") == ["school_id", "school_year"]
        assert panel.get("entity_key") == "school_id"
        assert panel.get("year_key") == "school_year"
        assert panel.get("file_format") == "parquet"

    def test_scoping_policy_buckets(self, project_config: dict):
        policy = project_config.get("scoping_policy", {})
        active = policy.get("candidate_active_statuses", [])
        inactive = policy.get("candidate_inactive_statuses", [])
        review = policy.get("transition_review_statuses", [])

        assert "Open" in active
        assert "New" in active

        assert "Closed" in inactive
        assert "Inactive" in inactive
        assert "Future" in inactive

        # Ambiguous categories must NOT be automatically treated as inactive
        assert "Added" in review
        assert "Changed Boundary/Agency" in review
        assert "Reopened" in review

        # Ensure active, inactive, and review buckets are mutually exclusive
        assert set(active).isdisjoint(set(inactive))
        assert set(active).isdisjoint(set(review))
        assert set(inactive).isdisjoint(set(review))


class TestSourcesConfigContract:
    """Validate sources.yaml against verified NCES CCD data layouts."""

    def test_all_components_present(self, sources_config: dict):
        components = sources_config.get("components", {})
        assert "directory" in components
        assert "membership" in components
        assert "staff" in components

    @pytest.mark.parametrize("comp_name", ["directory", "membership", "staff"])
    def test_five_years_per_component(self, sources_config: dict, comp_name: str):
        comp = sources_config["components"][comp_name]
        files = comp.get("files", {})
        expected_years = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"]
        for y in expected_years:
            assert y in files, f"School year {y} missing in {comp_name}"
            y_info = files[y]
            assert "filename" in y_info
            assert "path" in y_info

    def test_membership_052_contract_indicator_and_panel_rule(self, sources_config: dict):
        m52 = sources_config["components"]["membership"]
        contract = m52.get("total_indicator_contract", {})
        assert (
            contract.get("primary_choice")
            == "Derived - Education Unit Total minus Adult Education Count"
        )
        assert contract.get("secondary_choice") == "Education Unit Total"
        assert "primary_panel_rule" in contract
        assert "1:1" in contract.get("primary_panel_rule", "")

    def test_verified_column_counts(self, sources_config: dict):
        comps = sources_config["components"]
        assert comps["directory"]["verified_column_count"] == 65
        assert comps["membership"]["verified_column_count"] == 18
        assert comps["staff"]["verified_column_count"] == 15

    def test_deterministic_encoding_cascade(self, sources_config: dict):
        protocol = sources_config.get("ingestion_protocol", {})
        assert protocol.get("encoding_policy") == "deterministic_cascade"
        assert protocol.get("primary_encoding") == "utf-8"
        assert protocol.get("fallback_encoding") == "windows-1252"
        assert protocol.get("silent_decode_error_allowed") is False
        encodings = protocol.get("candidate_encodings", [])
        assert encodings[0] == "utf-8"
        assert encodings[1] == "windows-1252"
        # latin-1 must never precede strict decoders
        assert "latin-1" not in encodings[:2]


class TestColumnMappingContract:
    """Validate column_mapping.yaml standardized schema mappings."""

    def test_directory_mappings(self, column_mapping_config: dict):
        dir_cfg = column_mapping_config.get("directory", {})
        mappings = dir_cfg.get("mappings", {})
        assert mappings["NCESSCH"]["target"] == "school_id"
        assert mappings["LEAID"]["target"] == "district_id"
        assert mappings["FIPST"]["target"] == "state_fips"
        assert mappings["ST"]["target"] == "state_code"
        assert mappings["SCH_NAME"]["target"] == "school_name"
        assert mappings["SY_STATUS_TEXT"]["target"] == "school_status"
        assert mappings["SCH_TYPE_TEXT"]["target"] == "school_type"
        assert mappings["LEVEL"]["target"] == "school_level"

    def test_membership_mappings(self, column_mapping_config: dict):
        mem_cfg = column_mapping_config.get("membership", {})
        mappings = mem_cfg.get("mappings", {})
        assert mappings["NCESSCH"]["target"] == "school_id"
        assert mappings["STUDENT_COUNT"]["target"] == "total_students"
        assert mappings["TOTAL_INDICATOR"]["target"] == "enrollment_total_indicator"
        assert mappings["DMS_FLAG"]["target"] == "enrollment_data_flag"

    def test_staff_mappings(self, column_mapping_config: dict):
        staff_cfg = column_mapping_config.get("staff", {})
        mappings = staff_cfg.get("mappings", {})
        assert mappings["NCESSCH"]["target"] == "school_id"
        assert mappings["TEACHERS"]["target"] == "teacher_fte"
        assert mappings["TOTAL_INDICATOR"]["target"] == "staff_total_indicator"
        assert mappings["DMS_FLAG"]["target"] == "teacher_data_flag"

    def test_school_year_standardization_rule(self, column_mapping_config: dict):
        std_rules = column_mapping_config.get("standardization_rules", {})
        sy_rule = std_rules.get("school_year", {})
        assert sy_rule.get("raw_format") == "YYYY-YYYY"
        assert sy_rule.get("canonical_format") == "YYYY-YY"
        assert sy_rule.get("canonical_length") == 7
        assert "[:4]" in sy_rule.get("transformation", "")

    def test_all_components_standardize_school_year(self, column_mapping_config: dict):
        for comp in ["directory", "membership", "staff"]:
            mappings = column_mapping_config[comp]["mappings"]
            assert "SCHOOL_YEAR" in mappings
            sy = mappings["SCHOOL_YEAR"]
            assert sy["target"] == "school_year"
            assert sy["raw_format"] == "YYYY-YYYY"
            assert sy["canonical_format"] == "YYYY-YY"
            assert sy["length"] == 7
            assert "[:4]" in sy["transformation"]


class TestQualityRulesContract:
    """Validate quality_rules.yaml constraints and policies."""

    def test_identifier_rules(self, quality_rules_config: dict):
        rules = quality_rules_config.get("identifier_rules", {})
        assert rules["school_id"]["length"] == 12
        assert rules["school_id"]["preserve_leading_zeros"] is True
        assert rules["district_id"]["length"] == 7
        assert rules["state_fips"]["length"] == 2
        assert rules["school_year"]["length"] == 7
        assert rules["school_year"]["canonical_format"] == "YYYY-YY"

    def test_membership_grain_isolation_rule(self, quality_rules_config: dict):
        m_rules = quality_rules_config.get("table_grain_rules", {}).get("membership", {})
        assert m_rules["filtered_grain"] == ["school_id", "school_year"]
        assert (
            m_rules["primary_panel_indicator"]
            == "Derived - Education Unit Total minus Adult Education Count"
        )
        assert "grain_isolation_rule" in m_rules

    def test_join_semantics_and_cardinality(self, quality_rules_config: dict):
        joins = quality_rules_config.get("join_rules", {})
        assert joins.get("spine_table") == "directory"
        for j in joins.get("joins", []):
            # Target tables have unique keys, guaranteeing at most one match per directory record (1:0..1)
            assert j.get("cardinality") == "one_to_zero_or_one", (
                f"Join to {j.get('table')} must be one_to_zero_or_one"
            )
            assert j.get("target_key_unique") is True
            assert j.get("unmatched_spine_permitted") is True

        post_join = joins.get("post_join_invariants", {})
        assert post_join.get("grain") == ["school_id", "school_year"]
        assert post_join.get("cardinality") == "one_to_zero_or_one"
        assert post_join.get("unique_key_enforcement") is True
        assert post_join.get("duplicate_key_policy") == "fail"
        assert "unmatched" in post_join.get("unmatched_keys_handling", "").lower()

    def test_status_scoping_rules_separate_transitions(self, quality_rules_config: dict):
        scoping = quality_rules_config.get("scoping_rules", {}).get("active_school_status", {})
        active = scoping.get("candidate_active_statuses", [])
        inactive = scoping.get("candidate_inactive_statuses", [])
        review = scoping.get("transition_review_statuses", [])

        assert "Open" in active and "New" in active
        assert "Closed" in inactive
        assert "Added" in review
        assert "Changed Boundary/Agency" in review
        assert "Reopened" in review


class TestKpiDefinitionsContract:
    """Validate kpi_definitions.yaml formulas, units, caveats, and tier hierarchy."""

    @pytest.mark.parametrize(
        "kpi_name",
        [
            "total_students",
            "teacher_fte",
            "student_teacher_ratio",
            "enrollment_growth_yoy_pct",
            "teacher_fte_growth_yoy_pct",
            "ratio_growth_yoy_pct",
            "growth_gap_pct_points",
            "peer_group_benchmarking",
            "resource_pressure_tier",
            "data_quality_metrics",
        ],
    )
    def test_kpi_present(self, kpi_definitions_config: dict, kpi_name: str):
        kpis = kpi_definitions_config.get("kpis", {})
        assert kpi_name in kpis, (
            f"KPI or contract section {kpi_name} missing from kpi_definitions.yaml"
        )

    def test_student_teacher_ratio_caveat_and_zero_handling(self, kpi_definitions_config: dict):
        kpi = kpi_definitions_config["kpis"]["student_teacher_ratio"]
        assert "zero_denominator_handling" in kpi
        assert "null" in kpi["zero_denominator_handling"].lower()
        assert "class size" in kpi["caveats"].lower()

    def test_ratio_growth_yoy_pct_contract(self, kpi_definitions_config: dict):
        kpi = kpi_definitions_config["kpis"]["ratio_growth_yoy_pct"]
        assert "student_teacher_ratio" in kpi["formula"]
        assert "%" in kpi["unit"]
        assert "zero_denominator_handling" in kpi
        assert "null" in kpi["zero_denominator_handling"].lower()
        assert "consecutive" in str(kpi["eligibility_criteria"]).lower()

    def test_growth_gap_formula(self, kpi_definitions_config: dict):
        kpi = kpi_definitions_config["kpis"]["growth_gap_pct_points"]
        assert "enrollment_growth_yoy_pct" in kpi["formula"]
        assert "teacher_fte_growth_yoy_pct" in kpi["formula"]
        assert "%p" in kpi["unit"]

    def test_peer_group_benchmarking_scope(self, kpi_definitions_config: dict):
        bench = kpi_definitions_config["kpis"].get("peer_group_benchmarking", {})
        eligible = bench.get("eligible_p90_peer_groups", {})
        assert eligible.get("school_type") == "Regular School"
        assert set(eligible.get("school_levels", [])) == {"Elementary", "Middle", "High"}

        # Issue 5: Unsupported numerical claim (>15,000 schools) must be removed
        assert "15,000" not in str(bench)
        assert "> 15,000" not in str(bench)
        assert (
            "Exploratory analysis and peer-group evaluation is responsible for reporting actual peer-group stratum sizes"
            in eligible.get("rationale", "")
        )

        # Issue 4: Complete unbenchmarked-level handling including Secondary, Not applicable, Adult Education, and catch-all
        unbenchmarked = bench.get("unbenchmarked_peer_groups", {})
        assert "Special Education School" in unbenchmarked.get("non_regular_school_types", [])
        assert "Alternative School" in unbenchmarked.get("non_regular_school_types", [])
        observed_levels = unbenchmarked.get("observed_non_eligible_levels", [])
        for lvl in [
            "Secondary",
            "Not applicable",
            "Adult Education",
            "Other",
            "Prekindergarten",
            "Ungraded",
            "Not reported",
            "Missing",
        ]:
            assert lvl in observed_levels

        assert "catch_all_rule" in unbenchmarked
        assert (
            "outside the exact set {'Elementary', 'Middle', 'High'}"
            in unbenchmarked["catch_all_rule"]
        )
        assert "handling_policy" in unbenchmarked

        # Issue 3: Peer group status dimension and unbenchmarked interpretation caveat
        status_dim = bench.get("peer_group_status_dimension", {})
        assert (
            status_dim.get("categories", {}).get("benchmarked") == "Benchmarked Regular Peer Group"
        )
        assert (
            status_dim.get("categories", {}).get("unbenchmarked")
            == "Unbenchmarked / Specialized Peer Group"
        )

        p6_rules = kpi_definitions_config["kpis"]["resource_pressure_tier"]["rules"][
            "priority_6_stable_balanced"
        ]
        assert "unbenchmarked_interpretation_caveat" in p6_rules
        assert (
            "does not imply or certify that the school's absolute staffing levels"
            in p6_rules["unbenchmarked_interpretation_caveat"].lower()
        )

    def test_resource_pressure_tier_hierarchy(self, kpi_definitions_config: dict):
        tier_cfg = kpi_definitions_config["kpis"]["resource_pressure_tier"]
        order = tier_cfg.get("evaluation_order", {})
        assert order.get("priority_1") == "Incomplete Data or Status Review"
        assert order.get("priority_2") == "High Current Ratio"
        assert order.get("priority_3") == "Rapidly Rising Ratio"
        assert order.get("priority_4") == "Staffing Growth Deficit"
        assert order.get("priority_5") == "Growth Unassessed / Incomplete Growth Data"
        assert order.get("priority_6") == "Stable / Balanced"

        rules = tier_cfg.get("rules", {})
        assert "tie_handling" in rules["priority_2_high_current_ratio"]
        assert "peer_group_scope" in rules["priority_2_high_current_ratio"]
        assert rules["priority_3_rapidly_rising_ratio"].get("provisional_threshold") is True
        assert rules["priority_4_staffing_growth_deficit"].get("provisional_threshold") is True


class TestTierClassificationBehavior:
    """Simulate and validate the hierarchical, mutually exclusive tier categorization logic."""

    def get_peer_group_status(self, school_type: str, school_level: str) -> str:
        """Orthogonal peer group status dimension.

        Adheres strictly to the catch-all rule: ONLY Regular School within {'Elementary', 'Middle', 'High'}
        is eligible for P90 decile benchmarking. Every other school level and school type is unbenchmarked.
        """
        eligible_levels = {"Elementary", "Middle", "High"}
        if school_type == "Regular School" and school_level in eligible_levels:
            return "Benchmarked Regular Peer Group"
        return "Unbenchmarked / Specialized Peer Group"

    def classify_school(
        self,
        total_students: float | None,
        teacher_fte: float | None,
        teacher_data_flag: str,
        is_operational: bool,
        school_status: str = "Open",
        school_type: str = "Regular School",
        school_level: str = "Elementary",
        ratio: float | None = None,
        p90: float | None = 20.0,
        has_prior_year_record: bool = True,
        ratio_growth_pct: float | None = 0.0,
        growth_gap_pp: float | None = 0.0,
        tau_ratio_rise: float = 15.0,
        tau_growth_gap: float = 5.0,
    ) -> str:
        """Reference implementation of tier decision hierarchy."""
        # Priority 1: Incomplete Data or Status Review
        transition_statuses = {"Added", "Changed Boundary/Agency", "Reopened"}
        if (
            total_students is None
            or teacher_fte is None
            or teacher_data_flag != "Reported"
            or teacher_fte == 0.0
            or not is_operational
            or school_status in transition_statuses
            or ratio is None
        ):
            return "Incomplete Data or Status Review"

        # Priority 2: High Current Ratio (evaluated strictly on regular schools with standard levels)
        is_eligible_p90 = (
            self.get_peer_group_status(school_type, school_level)
            == "Benchmarked Regular Peer Group"
            and p90 is not None
        )
        if is_eligible_p90 and ratio >= p90:
            return "High Current Ratio"

        # Priority 5: Growth Unassessed / Incomplete Growth Data
        # Triggered if prior-year record is missing OR if growth metrics could not be calculated
        # (e.g. prior year FTE was missing or zero, resulting in None growth metrics).
        growth_metrics_valid = (
            has_prior_year_record and ratio_growth_pct is not None and growth_gap_pp is not None
        )
        if not growth_metrics_valid:
            return "Growth Unassessed / Incomplete Growth Data"

        # Priority 3: Rapidly Rising Ratio (provisional threshold)
        if ratio_growth_pct >= tau_ratio_rise:
            return "Rapidly Rising Ratio"

        # Priority 4: Staffing Growth Deficit (provisional threshold)
        if growth_gap_pp >= tau_growth_gap:
            return "Staffing Growth Deficit"

        # Priority 6: Stable / Balanced
        return "Stable / Balanced"

    def test_incomplete_data_and_status_review_priority(self):
        # Missing enrollment
        assert (
            self.classify_school(None, 25.0, "Reported", True, ratio=None)
            == "Incomplete Data or Status Review"
        )
        # Non-reported teacher data
        assert (
            self.classify_school(500, None, "Missing", True, ratio=None)
            == "Incomplete Data or Status Review"
        )
        # Zero teacher FTE
        assert (
            self.classify_school(500, 0.0, "Reported", True, ratio=None)
            == "Incomplete Data or Status Review"
        )
        # Non-operational school
        assert (
            self.classify_school(500, 25.0, "Reported", False, ratio=20.0)
            == "Incomplete Data or Status Review"
        )
        # Transition review statuses
        assert (
            self.classify_school(500, 25.0, "Reported", True, school_status="Added", ratio=20.0)
            == "Incomplete Data or Status Review"
        )
        assert (
            self.classify_school(
                500, 25.0, "Reported", True, school_status="Changed Boundary/Agency", ratio=20.0
            )
            == "Incomplete Data or Status Review"
        )
        assert (
            self.classify_school(500, 25.0, "Reported", True, school_status="Reopened", ratio=20.0)
            == "Incomplete Data or Status Review"
        )

    def test_high_ratio_priority_and_tie_handling(self):
        # Regular school ratio >= P90 gets High Current Ratio even if growth gap is very high
        assert (
            self.get_peer_group_status("Regular School", "Elementary")
            == "Benchmarked Regular Peer Group"
        )
        assert (
            self.classify_school(
                600,
                20.0,
                "Reported",
                True,
                ratio=30.0,
                p90=25.0,
                ratio_growth_pct=20.0,
                growth_gap_pp=10.0,
            )
            == "High Current Ratio"
        )
        # Exact tie: ratio == P90
        assert (
            self.classify_school(
                500,
                20.0,
                "Reported",
                True,
                ratio=25.0,
                p90=25.0,
                ratio_growth_pct=0.0,
                growth_gap_pp=0.0,
            )
            == "High Current Ratio"
        )

    def test_specialized_peer_group_bypasses_p90(self):
        # Special Education school with ratio >= regular P90 must NOT be assigned to regular High Current Ratio
        assert (
            self.get_peer_group_status("Special Education School", "Elementary")
            == "Unbenchmarked / Specialized Peer Group"
        )
        result = self.classify_school(
            50,
            2.0,
            "Reported",
            True,
            school_type="Special Education School",
            school_level="Elementary",
            ratio=25.0,
            p90=20.0,
            has_prior_year_record=True,
            ratio_growth_pct=2.0,
            growth_gap_pp=1.0,
        )
        assert result == "Stable / Balanced"

        # Alternative school with high growth gap bypasses P90 and gets Staffing Growth Deficit
        assert (
            self.get_peer_group_status("Alternative School", "High")
            == "Unbenchmarked / Specialized Peer Group"
        )
        alt_result = self.classify_school(
            100,
            4.0,
            "Reported",
            True,
            school_type="Alternative School",
            school_level="High",
            ratio=25.0,
            p90=20.0,
            has_prior_year_record=True,
            ratio_growth_pct=2.0,
            growth_gap_pp=8.0,
        )
        assert alt_result == "Staffing Growth Deficit"

    def test_complete_unbenchmarked_level_handling_and_unexpected_values(self):
        # Issue 4: Validate observed non-eligible levels and unexpected/unknown levels
        non_eligible_levels = [
            "Secondary",
            "Not applicable",
            "Adult Education",
            "Other",
            "Prekindergarten",
            "Ungraded",
            "Not reported",
            "Missing",
            "Unknown Level",
            "Combined Elementary-Secondary",
            "Vocational High",
            "",
            "None",
        ]
        for level in non_eligible_levels:
            # Must be classified as unbenchmarked peer group
            status = self.get_peer_group_status("Regular School", level)
            assert status == "Unbenchmarked / Specialized Peer Group", (
                f"Level '{level}' was not classified as unbenchmarked"
            )

            # Must bypass Priority 2 even when ratio exceeds regular P90
            result = self.classify_school(
                400,
                16.0,
                "Reported",
                True,
                school_type="Regular School",
                school_level=level,
                ratio=25.0,
                p90=20.0,
                has_prior_year_record=True,
                ratio_growth_pct=2.0,
                growth_gap_pp=1.0,
            )
            assert result == "Stable / Balanced", f"Level '{level}' failed to bypass Priority 2"

    def test_unbenchmarked_stable_balanced_interpretation_and_status(self):
        # Issue 3: Validate that unbenchmarked schools evaluating to Stable / Balanced
        # preserve the 6-tier taxonomy while explicitly having peer_group_status = 'Unbenchmarked / Specialized Peer Group'
        # and that this label only reflects trend thresholds not verified adequate staffing.
        test_cases = [
            ("Special Education School", "Elementary"),
            ("Regular School", "Secondary"),
            ("Regular School", "Not applicable"),
            ("Regular School", "Adult Education"),
            ("Alternative School", "Other"),
        ]
        for s_type, s_level in test_cases:
            status = self.get_peer_group_status(s_type, s_level)
            tier = self.classify_school(
                200,
                10.0,
                "Reported",
                True,
                school_type=s_type,
                school_level=s_level,
                ratio=20.0,
                p90=15.0,
                has_prior_year_record=True,
                ratio_growth_pct=1.0,
                growth_gap_pp=1.0,
            )
            assert tier == "Stable / Balanced"
            assert status == "Unbenchmarked / Specialized Peer Group"

    def test_rapidly_rising_ratio_priority(self):
        # Ratio < P90, but ratio grew 20% (>= 15%)
        assert (
            self.classify_school(
                400,
                20.0,
                "Reported",
                True,
                ratio=20.0,
                p90=25.0,
                ratio_growth_pct=20.0,
                growth_gap_pp=2.0,
            )
            == "Rapidly Rising Ratio"
        )

    def test_staffing_growth_deficit(self):
        # Ratio < P90, not rapidly rising (ratio growth 5%), but growth gap >= 5.0 pp
        assert (
            self.classify_school(
                400,
                20.0,
                "Reported",
                True,
                ratio=20.0,
                p90=25.0,
                ratio_growth_pct=5.0,
                growth_gap_pp=7.5,
            )
            == "Staffing Growth Deficit"
        )

    def test_growth_unassessed_when_prior_year_missing_or_uncomputable(self):
        # Valid ratio, but base year (2018-19) with no prior-year record
        assert (
            self.classify_school(
                400,
                20.0,
                "Reported",
                True,
                ratio=20.0,
                p90=25.0,
                has_prior_year_record=False,
                ratio_growth_pct=None,
                growth_gap_pp=None,
            )
            == "Growth Unassessed / Incomplete Growth Data"
        )

        # Prior year record exists, but prior-year FTE was zero or missing so growth could not be calculated
        # CRITICAL: Must evaluate to Growth Unassessed, NEVER fall through to Stable / Balanced!
        assert (
            self.classify_school(
                400,
                20.0,
                "Reported",
                True,
                ratio=20.0,
                p90=25.0,
                has_prior_year_record=True,
                ratio_growth_pct=None,
                growth_gap_pp=None,
            )
            == "Growth Unassessed / Incomplete Growth Data"
        )

    def test_stable_balanced(self):
        # Valid ratio < P90, growth assessed, small gap
        assert (
            self.classify_school(
                400,
                20.0,
                "Reported",
                True,
                ratio=20.0,
                p90=25.0,
                has_prior_year_record=True,
                ratio_growth_pct=2.0,
                growth_gap_pp=1.0,
            )
            == "Stable / Balanced"
        )

    def test_provisional_thresholds_are_not_approved_policy(self, kpi_definitions_config: dict):
        tier_cfg = kpi_definitions_config["kpis"]["resource_pressure_tier"]["rules"]
        p3 = tier_cfg["priority_3_rapidly_rising_ratio"]
        p4 = tier_cfg["priority_4_staffing_growth_deficit"]
        assert p3.get("provisional_threshold") is True
        assert p4.get("provisional_threshold") is True
        assert "not an approved" in p3.get("unresolved_threshold", "").lower()
        assert "not an approved" in p4.get("unresolved_threshold", "").lower()


class TestForecastingConfigContract:
    """Validate forecasting.yaml constraints, models, and retrospective timeframe."""

    def test_school_level_forecasting_is_rejected(self, forecasting_config: dict):
        feasibility = forecasting_config.get("forecasting", {}).get("feasibility_assessment", {})
        school_lvl = feasibility.get("school_level", {})
        assert school_lvl.get("feasible") is False
        assert "indefensible" in school_lvl.get("rationale", "").lower()

    def test_aggregate_forecasting_is_enabled(self, forecasting_config: dict):
        feasibility = forecasting_config.get("forecasting", {}).get("feasibility_assessment", {})
        agg_lvl = feasibility.get("aggregate_level", {})
        assert agg_lvl.get("feasible") is True
        assert agg_lvl.get("aggregation_grain") == "state_level"

    def test_forecast_horizon_and_retrospective_benchmark(self, forecasting_config: dict):
        fc = forecasting_config.get("forecasting", {})
        scope = fc.get("scope", {})
        assert scope.get("forecast_horizon_years") == 1
        assert scope.get("benchmark_target_year") == "2023-24"
        assert "retrospective" in scope.get("timeframe_framing", "").lower()

        models = fc.get("candidate_models", {})
        assert "naive_persistence" in models
        assert "drift" in models
        assert "moving_average_3yr" in models

    def test_retrospective_projection_accuracy_limitation_and_backtests(
        self, forecasting_config: dict
    ):
        fc = forecasting_config.get("forecasting", {})
        scope = fc.get("scope", {})
        framing = scope.get("timeframe_framing", "").lower()
        # Must explicitly state that 2023-24 forecast accuracy cannot be evaluated in this workspace
        assert "cannot be evaluated" in framing
        # Must note that empirical accuracy is evaluated on backtests
        assert "backtesting" in framing

    def test_validation_backtesting_and_metrics(self, forecasting_config: dict):
        fc = forecasting_config.get("forecasting", {})
        val = fc.get("validation_and_backtesting", {})
        assert "walk-forward" in val.get("method", "").lower()
        folds = val.get("folds", {})
        assert "fold_1" in folds and "fold_2" in folds
        assert folds["fold_1"]["test_year"] == "2021-22"
        assert folds["fold_2"]["test_year"] == "2022-23"
        metrics = val.get("metrics", {})
        assert "mae" in metrics
        assert "wape" in metrics
        assert "mape" in metrics
