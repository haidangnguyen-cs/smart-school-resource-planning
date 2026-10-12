# Executive Briefing Deck: Smart School Resource Planning

## Presentation Overview
* **Target Audience**: School District Superintendents, State Boards of Education, Legislative Budget Analysts
* **Length**: 15–20 minutes + Q&A
* **Format**: 10 Core Slides with Analytical Visuals

---

### Slide 1: Title & Strategic Purpose
* **Title**: Smart School Resource Planning: Evidence-Based Analytics & Decision Support
* **Subtitle**: Longitudinal NCES Common Core Analysis (2018–19 to 2022–23)
* **Key Talking Points**:
  - Transitioning from reactive budgeting to data-driven resource planning.
  - Rigorous data cleaning: separating true staffing shortages from administrative reporting anomalies.

### Slide 2: The Macro Picture: National Enrollment & Staffing Trajectory
* **Visual**: `outputs/figures/longitudinal_trends.png`
* **Key Talking Points**:
  - 49.6M public school students served across ~98.8k operational schools.
  - COVID-19 impact: -2.6% contraction in 2020–21, followed by stabilization.
  - National weighted ratio stable at ~15.5:1, but macro stability conceals local pressure points.

### Slide 3: Data Integrity: Why Raw Ratios Mislead
* **Visual**: Data Quality & Reporting Completeness Table
* **Key Talking Points**:
  - The zero vs. missing distinction: negative codes normalized, not zeroed.
  - Structural breaks in major states (CA, IL, NV, WA) require explicit audit flags.
  - Why ratio != class size: defining the metric accurately.

### Slide 4: Multi-Tier Resource Pressure Triage
* **Visual**: `outputs/figures/resource_pressure_tiers.png`
* **Key Talking Points**:
  - The Six Priority Tiers: from Administrative Review (P1) to Extreme Pressure (P2).
  - Preventing misallocation: auditing 4.7% of schools in P1 before spending capital.
  - Focusing intervention on 8.6% of schools exceeding peer P90 thresholds (P2).

### Slide 5: Geographic & School-Level Variations
* **Visual**: `outputs/figures/ratio_distribution.png`
* **Key Talking Points**:
  - Ratio variations across Primary, Middle, High, and Specialized facilities.
  - State-level disparities: high-ratio jurisdictions vs. low-ratio states.
  - Peer group normalization (State x Level) ensures fair comparisons.

### Slide 6: Forecasting Feasibility: Honest Science vs. False Precision
* **Visual**: Model Comparison Chart (`outputs/figures/backtest_model_comparison.png`)
* **Key Talking Points**:
  - Why school-level machine learning models fail on T=5 annual data points.
  - State aggregate forecasting feasibility: achieving 1.1%–1.5% WAPE with simple drift baselines.
  - Rejecting over-parameterized models (ARIMA, Prophet) in favor of defensible benchmarks.

### Slide 7: Scenario Planning & Policy Target Simulations
* **Visual**: `outputs/figures/retrospective_scenario_projections.png`
* **Key Talking Points**:
  - 2023–24 retrospective baseline projections and +/-2% scenario bands.
  - Implied staffing demand: how student enrollment shifts drive required teacher FTE under constant vs. policy target ratios.

### Slide 8: Interactive Decision-Support Dashboard
* **Visual**: Streamlit Dashboard Architecture Diagram & UI Walkthrough
* **Key Talking Points**:
  - Dynamic filtering by Year, State, School Level, and Charter Status.
  - Live triage queue inspection and CSV export for field teams.
  - Policy ratio slider for immediate district-level budget simulations.

### Slide 9: Core Policy Recommendations
* **Key Talking Points**:
  - **SEAs**: Mandate strict FTE reporting; track common school lineages.
  - **Districts**: Implement two-stage triage protocol before allocating FTEs.
  - **Analysts**: Smooth over 3-year windows; calibrate thresholds to local contracts.

### Slide 10: Conclusion & Next Steps
* **Key Talking Points**:
  - Production readiness of data pipelines and dashboards.
  - Phased rollout to regional planning committees.
  - Questions and Stakeholder Discussion.
