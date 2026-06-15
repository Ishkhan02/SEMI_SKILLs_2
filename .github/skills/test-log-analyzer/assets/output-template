## Chat Response Template — Test Log Analyzer

### Key findings:
- **Input file:** {{input_file}}
- **Total parts:** {{total_parts}}
- **Yield:** {{yield_percent}}%
- **Passing parts:** {{passing_parts}}
- **Failing parts:** {{failing_parts}}
- **Total failed test events:** {{failed_test_events}}
- **Top failing tests:**
{{top_failing_tests_bullets}}
- **Most failure-heavy sites:**
{{site_failure_bullets}}

### Optional 6σ Gaussian distribution analysis
{{sigma_analysis_section}}

### Placeholder guidance

#### {{top_failing_tests_bullets}}
Use nested bullets. Example:
- `Coff_RF1_1880M` — 4 failures
- `Cont_A1_to_GND` — 4 failures
- `Roff_DC_RF1_AOFF` — 4 failures

#### {{site_failure_bullets}}
Use nested bullets. Example:
- `Site 9` — 6 failures
- `Site 6` — 4 failures
- `Site 7` — 4 failures

#### {{sigma_analysis_section}}
If no sigma test was requested, output:
- Not requested.

If sigma analysis was requested, use this shape for each requested test:

#### `<Matched Test Name>`
- Match rule: exact name | partial name | test number
- Samples: `<count>`
- Mean: `<mean> <units>`
- Std dev (σ): `<sigma> <units>`
- Min / Max: `<min> <units>` / `<max> <units>`
- Mean - 3σ: `<lower_3sigma> <units>`
- Mean + 3σ: `<upper_3sigma> <units>`
- 6σ width: `<six_sigma_width> <units>`
- Limits: LSL=`<lsl>` USL=`<usl>`
- Cp / Cpk: `<cp>` / `<cpk>`
- Plot: `<plot_path>`
