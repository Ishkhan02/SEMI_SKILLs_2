---
name: test-log-analyzer
description: Analyze semiconductor test logs (especially STDF files) and produce a concise markdown summary of yield, dominant failing tests, site concentration, and optional 6σ Gaussian analysis for a user-specified test. Use this skill whenever the user asks to summarize STDF/ATDF logs, explain yield fallout, identify top failing tests or sites, compare lots by failure signature, or calculate a Gaussian / normal-distribution / 6-sigma view for a named measurement such as Cap_Voltage_After_Discharge, Cont_C1_to_GND, Ron_DC_RF1on_AOFF, or RF1_Leakage_AOFF_Current.
compatibility: Python 3.10+ with pandas, matplotlib, pystdf
---

# Test Log Analyzer

This skill turns raw semiconductor test logs into a fast engineering summary. It uses the bundled `analyze_test_logs.py` script to parse STDF records, compute yield/failure metrics, and optionally generate a **6σ Gaussian distribution analysis** for one or more user-specified tests.

## When to use this skill

Use this skill when the user asks to:
- summarize an STDF or ATDF log
- report yield, passing parts, failing parts, top failing tests, or failure-heavy sites
- compare fail signatures between runs or lots
- explain which tests dominate fallout
- run a **Gaussian / normal-distribution / 6-sigma** analysis for a test name or test number
- extract all measurements for a named test like `Cap_Voltage_After_Discharge`, `Cont_C1_to_GND`, `Calculate_Oscillator_freq`, `Ron_DC_RF1on_AOFF`, or `RF1_Leakage_AOFF_Current`

## Bundled files

- `scripts/analyze_test_logs.py` — deterministic parser/report generator
- `assets/output-template.md` — markdown response template

## Core rules

1. **Use the script instead of manually summarizing logs.** The script is the source of truth for parsing records and counting failures.
2. **Do not guess the sigma target.** If the user wants Gaussian / 6σ analysis but did not specify an exact test name or test number, ask for it first.
3. **Use PRR for part-level yield.** Part-level pass/fail must come from PRR records when available.
4. **Use PTR/FTR for event-level fallout.** Top failing tests and site concentration come from failed test events, not from PRR alone.
5. **6σ analysis is measurement-only.** Run Gaussian analysis only on numeric measurement records (typically PTR), not on purely functional pass/fail tests unless a numeric result exists.
6. **Report matching behavior clearly.** If the requested sigma target is matched by exact name, partial name, or test number, say which rule matched.
7. **If the requested test has too few samples, say so.** Fewer than 2 numeric samples is not enough for a meaningful standard deviation.
8. **Preserve original test names.** Never rename the test in the report.

## Required inputs

| Input | Required? | Notes |
|---|---|---|
| STDF / ATDF log file path | Yes | Primary input |
| Response shape | No | Default: markdown summary using `assets/output-template.md` |
| Sigma analysis target test name or test number | Only for 6σ analysis | Ask if missing |
| Top-N cutoff | No | Default = 10 |

## Workflow

### Step 1 — Confirm the request shape

Identify whether the user wants:
1. **Summary only** — yield, top failing tests, failing sites
2. **Summary + sigma analysis** — same summary plus a Gaussian section for one or more user-selected tests
3. **Sigma only** — extract a test's raw measurements and compute the distribution view

### Step 2 — Gather only missing blocking inputs

Ask only when one of these is missing:
- log file path
- exact sigma target when the user asked for Gaussian / 6σ analysis

If the user provided a loose description such as “leakage test”, ask for the exact test name or test number as shown in the log.

### Step 3 — Run the bundled script

Default command pattern:

```bash
python scripts/analyze_test_logs.py <input.std>   --template assets/output-template.md   --output report.md
```

When Gaussian analysis is requested:

```bash
python scripts/analyze_test_logs.py <input.std>   --template assets/output-template.md   --output report.md   --sigma-test "RF1_Leakage_AOFF_Current"   --plots-dir plots
```

For multiple sigma targets:

```bash
python scripts/analyze_test_logs.py <input.std>   --sigma-test "Cap_Voltage_After_Discharge"   --sigma-test "Ron_DC_RF1on_AOFF"
```

### Step 4 — Present the result using the template

Always return the markdown summary generated from `assets/output-template.md`.

If sigma analysis was requested, include:
- matched test name / test number
- number of numeric samples
- mean
- standard deviation
- min / max
- mean ± 3σ boundaries
- total 6σ width (= 6 × σ)
- Cp / Cpk if both limits exist and σ > 0
- plot file path if a histogram/gaussian image was generated

If the requested test cannot be found, say that explicitly and recommend the nearest exact test name from the file when available.

## Output contract

The script should produce:
1. A markdown report using `assets/output-template.md`
2. Optional PNG plots for each sigma target
3. Optional JSON metrics file when needed for downstream automation

## Response style

Keep the chat response compact and engineering-oriented:
- lead with the report
- then add 2–4 bullets of interpretation only if the user asked for analysis
- do not add generic RF advice unless the user asked for troubleshooting

## Validation checklist

After generating the report, verify:
- PRR-based total parts, pass count, and fail count are internally consistent
- failed test-event count equals the sum of failed PTR/FTR events used for ranking
- sigma section only includes numeric samples from the requested test
- Gaussian plot filenames are unique and sanitized
- report placeholders were fully resolved

## Notes about record usage

- `PRR` drives part-level yield
- `PTR` provides numeric parametric measurements and limits
- `FTR` provides functional test fail events
- `HBR` and `SBR` may be used to label bins when available

## Example user prompts that should trigger this skill

- “Analyze this STDF and tell me the top 10 failing tests and worst sites.”
- “Give me the same log summary, and also do a 6 sigma Gaussian for `RF1_Leakage_AOFF_Current`.”
- “Pull all measurements for `Cap_Voltage_After_Discharge` and show mean, sigma, 6σ span, and Cp/Cpk.”
- “Why is yield low in this run? Summarize fallout first, then plot Gaussian for `Ron_DC_RF1on_AOFF`.”
