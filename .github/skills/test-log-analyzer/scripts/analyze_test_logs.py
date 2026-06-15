#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze STDF test log files and optionally perform 6σ Gaussian analysis."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd

TOP_N = 10
DEFAULT_TEMPLATE_NAME = 'output-template.md'

def parse_float(value: object) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if text == '':
        return math.nan
    try:
        return float(text)
    except Exception:
        return math.nan

def parse_int(value: object) -> Optional[int]:
    num = parse_float(value)
    if math.isnan(num):
        return None
    return int(round(num))

def parse_flag_to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if text == '':
        return None
    try:
        return int(text, 16)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return None

def sanitize_file_stem(value: str) -> str:
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', value).strip('_')
    return stem or 'plot'

def infer_ptr_status(test_flag: object, result: float, lo_limit: float, hi_limit: float) -> str:
    flag_int = parse_flag_to_int(test_flag)
    if flag_int is not None and (flag_int & 0b11):
        return 'FAIL'
    if not math.isnan(lo_limit) and not math.isnan(result) and result < lo_limit:
        return 'FAIL'
    if not math.isnan(hi_limit) and not math.isnan(result) and result > hi_limit:
        return 'FAIL'
    return 'PASS'

def infer_ftr_status(test_flag: object, num_fail: Optional[int]) -> str:
    flag_int = parse_flag_to_int(test_flag)
    if flag_int is not None and (flag_int & 0b11):
        return 'FAIL'
    if num_fail is not None and num_fail > 0:
        return 'FAIL'
    return 'PASS'

def parse_stdf(stdf_path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    from pystdf.IO import Parser
    from pystdf.Writers import TextWriter

    with open(stdf_path, 'rb') as handle:
        parser = Parser(inp=handle)
        buffer = StringIO()
        parser.addSink(TextWriter(buffer))
        parser.parse()

    atdf_text = buffer.getvalue()
    lines = [line.strip() for line in atdf_text.splitlines() if line.strip()]

    active_part_by_site: Dict[str, str] = {}
    rows: List[Dict[str, object]] = []
    synthetic_part_counter = 0
    ignored_rows = 0

    for line in lines:
        if '|' not in line:
            ignored_rows += 1
            continue

        parts = line.split('|')
        rec_type = parts[0].strip().upper()
        payload = parts[1:]

        if rec_type == 'PIR':
            site_num = str(payload[1] if len(payload) > 1 else 'unknown')
            synthetic_part_counter += 1
            active_part_by_site[site_num] = f'P{synthetic_part_counter:06d}'
            continue

        if rec_type == 'PRR':
            site_num = str(payload[1] if len(payload) > 1 else 'unknown')
            part_flag = payload[2] if len(payload) > 2 else ''
            hard_bin = parse_int(payload[4] if len(payload) > 4 else None)
            soft_bin = parse_int(payload[5] if len(payload) > 5 else None)
            test_time_ms = parse_float(payload[8] if len(payload) > 8 else None)
            part_id = payload[9] if len(payload) > 9 and payload[9] else active_part_by_site.get(site_num)
            if not part_id:
                synthetic_part_counter += 1
                part_id = f'P{synthetic_part_counter:06d}'
            status = 'PASS' if hard_bin == 1 else 'FAIL'
            rows.append({
                'source_record': 'PRR',
                'part_id': str(part_id),
                'site_num': site_num,
                'test_num': None,
                'test_name': f'PART_RESULT_HBIN_{hard_bin}_SBIN_{soft_bin}',
                'result': test_time_ms,
                'lo_limit': math.nan,
                'hi_limit': math.nan,
                'units': 'ms',
                'status': status,
                'part_flag': str(part_flag),
                'hard_bin': hard_bin,
                'soft_bin': soft_bin,
            })
            active_part_by_site.pop(site_num, None)
            continue

        if rec_type == 'PTR':
            test_num = parse_int(payload[0] if len(payload) > 0 else None)
            site_num = str(payload[2] if len(payload) > 2 else 'unknown')
            test_flag = payload[3] if len(payload) > 3 else ''
            result = parse_float(payload[5] if len(payload) > 5 else None)
            test_name = payload[6] if len(payload) > 6 and payload[6] else f'TEST_{test_num}'
            lo_limit = parse_float(payload[13] if len(payload) > 13 else None)
            hi_limit = parse_float(payload[14] if len(payload) > 14 else None)
            units = payload[15] if len(payload) > 15 and payload[15] else ''
            part_id = active_part_by_site.get(site_num)
            if not part_id:
                synthetic_part_counter += 1
                part_id = f'P{synthetic_part_counter:06d}'
                active_part_by_site[site_num] = part_id
            rows.append({
                'source_record': 'PTR',
                'part_id': str(part_id),
                'site_num': site_num,
                'test_num': test_num,
                'test_name': str(test_name),
                'result': result,
                'lo_limit': lo_limit,
                'hi_limit': hi_limit,
                'units': str(units),
                'status': infer_ptr_status(test_flag, result, lo_limit, hi_limit),
                'test_flag': str(test_flag),
                'hard_bin': None,
                'soft_bin': None,
            })
            continue

        if rec_type == 'FTR':
            test_num = parse_int(payload[0] if len(payload) > 0 else None)
            site_num = str(payload[2] if len(payload) > 2 else 'unknown')
            test_flag = payload[3] if len(payload) > 3 else ''
            num_fail = parse_int(payload[8] if len(payload) > 8 else None)
            test_name = payload[21] if len(payload) > 21 and payload[21] else f'TEST_{test_num}'
            part_id = active_part_by_site.get(site_num)
            if not part_id:
                synthetic_part_counter += 1
                part_id = f'P{synthetic_part_counter:06d}'
                active_part_by_site[site_num] = part_id
            rows.append({
                'source_record': 'FTR',
                'part_id': str(part_id),
                'site_num': site_num,
                'test_num': test_num,
                'test_name': str(test_name),
                'result': float(num_fail) if num_fail is not None else math.nan,
                'lo_limit': math.nan,
                'hi_limit': math.nan,
                'units': 'count',
                'status': infer_ftr_status(test_flag, num_fail),
                'test_flag': str(test_flag),
                'hard_bin': None,
                'soft_bin': None,
            })
            continue

        ignored_rows += 1

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['source_record','part_id','site_num','test_num','test_name','result','lo_limit','hi_limit','units','status','hard_bin','soft_bin'])
    info = {
        'backend': 'pystdf + TextWriter',
        'records_parsed': len(df),
        'ignored_rows': ignored_rows,
        'unique_tests': int(df['test_name'].dropna().nunique()) if not df.empty else 0,
    }
    return df, info

def compute_metrics(df: pd.DataFrame, top_n: int = TOP_N) -> Dict[str, object]:
    prr_df = df[df['source_record'] == 'PRR'].copy()
    failed_events = df[(df['source_record'].isin(['PTR', 'FTR'])) & (df['status'] == 'FAIL')].copy()
    total_parts = int(prr_df['part_id'].nunique()) if not prr_df.empty else int(df['part_id'].nunique())
    passing_parts = int((prr_df['status'] == 'PASS').sum()) if not prr_df.empty else 0
    failing_parts = int((prr_df['status'] == 'FAIL').sum()) if not prr_df.empty else 0
    yield_percent = round((passing_parts / total_parts) * 100.0, 2) if total_parts else 0.0
    test_fail_counts = Counter(failed_events['test_name'].fillna('UNKNOWN_TEST').astype(str).tolist()) if not failed_events.empty else Counter()
    site_fail_counts = Counter(failed_events['site_num'].fillna('unknown').astype(str).tolist()) if not failed_events.empty else Counter()
    return {
        'total_parts': total_parts,
        'yield_percent': yield_percent,
        'passing_parts': passing_parts,
        'failing_parts': failing_parts,
        'failed_test_events': int(len(failed_events)),
        'top_failing_tests': dict(test_fail_counts.most_common(top_n)),
        'site_failures': dict(site_fail_counts.most_common(top_n)),
    }

def resolve_template_path(explicit_template: Optional[Path]) -> Path:
    if explicit_template:
        return explicit_template
    local = Path(DEFAULT_TEMPLATE_NAME)
    if local.exists():
        return local
    sibling = Path(__file__).resolve().with_name(DEFAULT_TEMPLATE_NAME)
    if sibling.exists():
        return sibling
    asset_path = Path(__file__).resolve().parents[1] / 'assets' / DEFAULT_TEMPLATE_NAME
    if asset_path.exists():
        return asset_path
    raise FileNotFoundError('Could not locate output-template.md')

def load_output_template(template_path: Optional[Path] = None) -> str:
    return resolve_template_path(template_path).read_text(encoding='utf-8')

def format_fail_bullets(counter: Dict[str, int], site_mode: bool = False) -> str:
    if not counter:
        return '- N/A'
    lines: List[str] = []
    for name, count in counter.items():
        if site_mode:
            lines.append(f'  - Site {name} — {count} failures')
        else:
            lines.append(f'  - {name} — {count} failures')
    return '\n'.join(lines)

def closest_candidates(df: pd.DataFrame, needle: str, max_items: int = 5) -> List[str]:
    names = sorted({str(v) for v in df['test_name'].dropna().tolist()})
    low = needle.casefold()
    starts = [name for name in names if name.casefold().startswith(low)]
    contains = [name for name in names if low in name.casefold() and name not in starts]
    return (starts + contains)[:max_items]

def extract_sigma_dataset(df: pd.DataFrame, requested_test: str) -> Dict[str, object]:
    ptr_df = df[(df['source_record'] == 'PTR') & pd.notna(df['result'])].copy()
    if ptr_df.empty:
        return {'requested': requested_test, 'matched_name': None, 'match_rule': 'not found', 'rows': ptr_df, 'candidates': []}
    ptr_df['test_name_str'] = ptr_df['test_name'].astype(str)
    requested = str(requested_test).strip()
    if requested.isdigit():
        exact_num = ptr_df[ptr_df['test_num'].astype('Int64') == int(requested)]
        if not exact_num.empty:
            return {'requested': requested_test, 'matched_name': str(exact_num.iloc[0]['test_name_str']), 'match_rule': 'test number', 'rows': exact_num}
    exact = ptr_df[ptr_df['test_name_str'].str.casefold() == requested.casefold()]
    if not exact.empty:
        return {'requested': requested_test, 'matched_name': str(exact.iloc[0]['test_name_str']), 'match_rule': 'exact name', 'rows': exact}
    partial = ptr_df[ptr_df['test_name_str'].str.casefold().str.contains(re.escape(requested.casefold()), regex=True)]
    if not partial.empty:
        matched_name = str(partial.iloc[0]['test_name_str'])
        narrowed = partial[partial['test_name_str'] == matched_name]
        return {'requested': requested_test, 'matched_name': matched_name, 'match_rule': 'partial name', 'rows': narrowed}
    return {'requested': requested_test, 'matched_name': None, 'match_rule': 'not found', 'rows': ptr_df.iloc[0:0], 'candidates': closest_candidates(ptr_df, requested)}

def compute_sigma_statistics(rows: pd.DataFrame) -> Dict[str, object]:
    values = pd.to_numeric(rows['result'], errors='coerce').dropna().astype(float)
    units_series = rows['units'].dropna().astype(str)
    units = units_series.mode().iat[0] if not units_series.empty else ''
    if values.empty:
        return {'sample_count': 0, 'units': units, 'mean': math.nan, 'std_dev': math.nan, 'min': math.nan, 'max': math.nan, 'lower_3sigma': math.nan, 'upper_3sigma': math.nan, 'six_sigma_width': math.nan, 'lsl': math.nan, 'usl': math.nan, 'cp': math.nan, 'cpk': math.nan}
    mean = float(values.mean())
    std_dev = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    lower_3sigma = mean - 3 * std_dev
    upper_3sigma = mean + 3 * std_dev
    six_sigma_width = 6 * std_dev
    lsl_values = pd.to_numeric(rows['lo_limit'], errors='coerce').dropna().astype(float)
    usl_values = pd.to_numeric(rows['hi_limit'], errors='coerce').dropna().astype(float)
    lsl = float(lsl_values.mode().iat[0]) if not lsl_values.empty else math.nan
    usl = float(usl_values.mode().iat[0]) if not usl_values.empty else math.nan
    cp = math.nan
    cpk = math.nan
    if std_dev > 0 and not math.isnan(lsl) and not math.isnan(usl):
        cp = (usl - lsl) / (6 * std_dev)
        cpk = min((usl - mean) / (3 * std_dev), (mean - lsl) / (3 * std_dev))
    return {'sample_count': int(len(values)), 'units': units, 'mean': mean, 'std_dev': std_dev, 'min': float(values.min()), 'max': float(values.max()), 'lower_3sigma': lower_3sigma, 'upper_3sigma': upper_3sigma, 'six_sigma_width': six_sigma_width, 'lsl': lsl, 'usl': usl, 'cp': cp, 'cpk': cpk, 'values': values}

def generate_sigma_plot(values: pd.Series, matched_name: str, stats: Dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / f"{sanitize_file_stem(matched_name)}_gaussian.png"
    plt.figure(figsize=(10, 6))
    bins = min(30, max(8, int(math.sqrt(len(values)))))
    plt.hist(values, bins=bins, density=True, alpha=0.65)
    mean = float(stats['mean'])
    sigma = float(stats['std_dev'])
    x_min = min(float(values.min()), mean - (4 * sigma if sigma > 0 else 1))
    x_max = max(float(values.max()), mean + (4 * sigma if sigma > 0 else 1))
    xs = pd.Series([x_min + (x_max - x_min) * i / 400 for i in range(401)])
    if sigma > 0:
        coeff = 1.0 / (sigma * math.sqrt(2 * math.pi))
        ys = coeff * ((-(xs - mean) ** 2) / (2 * sigma ** 2)).apply(math.exp)
        plt.plot(xs, ys, linewidth=2)
        plt.axvline(mean - 3 * sigma, linestyle='--', linewidth=1)
        plt.axvline(mean + 3 * sigma, linestyle='--', linewidth=1)
    plt.axvline(mean, linestyle=':', linewidth=1.5)
    units = str(stats.get('units') or '').strip()
    plt.title(f'Gaussian analysis — {matched_name}')
    plt.xlabel(f'Measurement ({units})' if units else 'Measurement')
    plt.ylabel('Density')
    plt.tight_layout()
    plt.savefig(plot_path, dpi=160)
    plt.close()
    return plot_path

def fmt(value: object, digits: int = 6) -> str:
    if value is None:
        return 'N/A'
    try:
        number = float(value)
    except Exception:
        return str(value)
    if math.isnan(number):
        return 'N/A'
    return f'{number:.{digits}g}'

def build_sigma_analysis_section(df: pd.DataFrame, sigma_tests: Iterable[str], plots_dir: Optional[Path]) -> str:
    requests = [str(item).strip() for item in sigma_tests if str(item).strip()]
    if not requests:
        return '- Not requested.'
    sections: List[str] = []
    for request in requests:
        dataset = extract_sigma_dataset(df, request)
        matched_name = dataset.get('matched_name')
        if not matched_name:
            suggestions = dataset.get('candidates') or []
            suggestion_text = ', '.join(f'`{name}`' for name in suggestions) if suggestions else 'N/A'
            sections.append('\n'.join([f'#### {request}', '- Match rule: not found', '- Samples: 0', f'- Closest candidates: {suggestion_text}']))
            continue
        rows = dataset['rows']
        stats = compute_sigma_statistics(rows)
        plot_path_text = 'N/A'
        if stats['sample_count'] >= 2 and plots_dir is not None:
            plot_path_text = str(generate_sigma_plot(stats['values'], matched_name, stats, plots_dir))
        units = str(stats.get('units') or '').strip()
        unit_suffix = f' {units}' if units else ''
        sections.append('\n'.join([
            f'#### {matched_name}',
            f"- Match rule: {dataset['match_rule']}" ,
            f"- Samples: {stats['sample_count']}" ,
            f"- Mean: {fmt(stats['mean'])}{unit_suffix}" ,
            f"- Std dev (σ): {fmt(stats['std_dev'])}{unit_suffix}" ,
            f"- Min / Max: {fmt(stats['min'])}{unit_suffix} / {fmt(stats['max'])}{unit_suffix}" ,
            f"- Mean - 3σ: {fmt(stats['lower_3sigma'])}{unit_suffix}" ,
            f"- Mean + 3σ: {fmt(stats['upper_3sigma'])}{unit_suffix}" ,
            f"- 6σ width: {fmt(stats['six_sigma_width'])}{unit_suffix}" ,
            f"- Limits: LSL={fmt(stats['lsl'])} USL={fmt(stats['usl'])}" ,
            f"- Cp / Cpk: {fmt(stats['cp'])} / {fmt(stats['cpk'])}" ,
            f"- Plot: {plot_path_text}" ,
        ]))
    return '\n\n'.join(sections)

def generate_report(df: pd.DataFrame, metrics: Dict[str, object], input_file: Path, template_path: Optional[Path], sigma_tests: Iterable[str], plots_dir: Optional[Path]) -> str:
    template = load_output_template(template_path)
    replacements = {
        '{{input_file}}': str(input_file),
        '{{total_parts}}': str(metrics['total_parts']),
        '{{yield_percent}}': f"{metrics['yield_percent']:.2f}",
        '{{passing_parts}}': str(metrics['passing_parts']),
        '{{failing_parts}}': str(metrics['failing_parts']),
        '{{failed_test_events}}': str(metrics['failed_test_events']),
        '{{top_failing_tests_bullets}}': format_fail_bullets(metrics.get('top_failing_tests', {}), site_mode=False),
        '{{site_failure_bullets}}': format_fail_bullets(metrics.get('site_failures', {}), site_mode=True),
        '{{sigma_analysis_section}}': build_sigma_analysis_section(df, sigma_tests, plots_dir),
    }
    report = template
    for key, value in replacements.items():
        report = report.replace(key, value)
    return report

def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Analyze STDF test logs and generate markdown summary')
    parser.add_argument('input_file', type=Path, help='Path to the STDF file')
    parser.add_argument('--template', type=Path, default=None, help='Path to markdown output template')
    parser.add_argument('--output', type=Path, default=Path('report.md'), help='Path to final markdown report')
    parser.add_argument('--json-output', type=Path, default=None, help='Optional JSON metrics output')
    parser.add_argument('--plots-dir', type=Path, default=None, help='Directory for optional Gaussian plots')
    parser.add_argument('--top-n', type=int, default=TOP_N, help='Top-N failing tests/sites to report')
    parser.add_argument('--sigma-test', action='append', default=[], help='Exact or partial test name, or test number, to analyze with Gaussian / 6σ statistics')
    return parser

def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    df, info = parse_stdf(args.input_file)
    metrics = compute_metrics(df, top_n=args.top_n)
    report = generate_report(df, metrics, args.input_file, args.template, args.sigma_test, args.plots_dir)
    args.output.write_text(report, encoding='utf-8')
    print(report)
    if args.json_output is not None:
        payload = {
            'input_file': str(args.input_file),
            'metrics': metrics,
            'parser_info': info,
            'sigma_tests': args.sigma_test,
        }
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
