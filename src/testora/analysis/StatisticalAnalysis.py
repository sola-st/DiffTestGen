#!/usr/bin/env python3
"""
Paired PR bootstrap comparisons of DiffTestGen against the other approaches.
Each comparison reports how DiffTestGen performed against one other tool, across the same PRs:
- Tool percentages: the average detection rate or coverage for each tool.
- Paired difference: DiffTestGen’s average minus the other tool’s average, in percentage points. 
    A positive value favors DiffTestGen; a negative value favors the compared tool.
- Confidence interval: the range of differences supported by the bootstrap analysis, adjusted for all eight comparisons. 
    If the interval excludes zero, the difference is statistically significant at the adjusted level; 
    if it includes zero, the results don’t establish a clear difference.
- PRs favoring / tied / favoring other tool: 
    for detection, how many PRs had a higher, equal, or lower average for DiffTestGen across the three repetitions.
- Mean PRs detected per run: the average number detected per run, derived from the detection rates.
"""
import csv
import io
import os
import random
from contextlib import redirect_stdout

TOOLS = ("Testora", "Testora++", "Only Coverage Feedback", "Only Access Information", "DiffTestGen")
BASELINES = TOOLS[:-1]
DIFFTESTGEN = "DiffTestGen"
FIELDS = {'Project', 'PR', 'Approach', 'Repetitions', 'change found', 'Coverage'}
CSV_PATH = os.path.join("data","results", "table_and_plots", "different_outputs_statistics", "pr_behavioral_changes_coverage.csv")
BOOTSTRAP_SAMPLES = 20000
RANDOM_SEED = 2026


def read_data():
    data = {}
    project = pr = approach = None
    with open(CSV_PATH, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError(f'Expected columns: {sorted(FIELDS)}')
        for line, row in enumerate(reader, 2):
            p, n, a = (row[k].strip() for k in ('Project', 'PR', 'Approach'))
            if p:
                project, pr, approach = p, None, None
            if n:
                pr, approach = n, None
            if a:
                approach = a
            if not all((project, pr, approach)) or approach not in TOOLS:
                raise ValueError(f'Line {line}: invalid or missing project, PR, or approach')
            rep = row['Repetitions'].strip()
            found = row['change found'].strip().lower()
            if rep not in ('0', '1', '2') or found not in ('true', 'false'):
                raise ValueError(f'Line {line}: invalid repetition or detection value')
            coverage = row['Coverage'].strip()
            if not coverage.endswith('%'):
                raise ValueError(f'Line {line}: coverage must be a percentage')
            try:
                cov = float(coverage[:-1])
            except ValueError as exc:
                raise ValueError(f'Line {line}: invalid coverage') from exc
            if not 0 <= cov <= 100:
                raise ValueError(f'Line {line}: coverage outside 0–100%')
            key = (project, pr)
            runs = data.setdefault(key, {}).setdefault(approach, {})
            if rep in runs:
                raise ValueError(f'Line {line}: duplicate PR, approach, and repetition')
            runs[rep] = (100.0 if found == 'true' else 0.0, cov)
    if not data:
        raise ValueError('No observations')
    for key, methods in data.items():
        if set(methods) != set(TOOLS) or any(set(runs) != {'0', '1', '2'} for runs in methods.values()):
            raise ValueError(f'{key}: expected both tools and repetitions 0, 1, 2')
    return data


def percentile(values, p):
    position = (len(values) - 1) * p
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def analyze(data, baseline, metric, n_boot, rng):
    pairs = []
    for methods in data.values():
        baseline_mean = sum(x[metric] for x in methods[baseline].values()) / 3
        difftestgen_mean = sum(x[metric] for x in methods[DIFFTESTGEN].values()) / 3
        pairs.append((baseline_mean, difftestgen_mean))
    n = len(pairs)
    diffs = [difftestgen - baseline for baseline, difftestgen in pairs]
    estimates = []
    for _ in range(n_boot):
        estimates.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    estimates.sort()
    # Bonferroni adjustment across four comparisons and two outcomes.
    lo, hi = percentile(estimates, .003125), percentile(estimates, .996875)
    print(f'\n{("Detection rate", "Union coverage")[metric]}: {baseline} vs DiffTestGen')
    print(f'  {baseline}: {sum(p[0] for p in pairs)/n:.2f}%')
    print(f'  DiffTestGen: {sum(p[1] for p in pairs)/n:.2f}%')
    print(f'  Paired difference: {sum(diffs)/n:+.2f} percentage points')
    print(f'  99.375% percentile bootstrap CI: [{lo:+.2f}, {hi:+.2f}] percentage points')
    print('  CI excludes zero:', 'yes' if lo > 0 or hi < 0 else 'no')
    if metric == 0:
        wins = sum(d > 1e-9 for d in diffs)
        losses = sum(d < -1e-9 for d in diffs)
        print(f'  PRs favoring DiffTestGen / tied / favoring {baseline}: {wins} / {n-wins-losses} / {losses}')
        print(f'  Mean PRs detected per run: {baseline} {sum(p[0] for p in pairs)/100:.2f}; DiffTestGen {sum(p[1] for p in pairs)/100:.2f}')


def main():
    try:
        data = read_data()
    except (ValueError, OSError, csv.Error) as exc:
        raise SystemExit(f'Error: {exc}') from exc
    results = io.StringIO()
    with redirect_stdout(results):
        print(f'Complete paired PRs: {len(data)}; bootstrap samples: {BOOTSTRAP_SAMPLES}; seed: {RANDOM_SEED}')
        print('Percentile intervals use Bonferroni adjustment across four comparisons and two outcomes.')
        rng = random.Random(RANDOM_SEED)
        for baseline in BASELINES:
            for metric in (0, 1):
                analyze(data, baseline, metric, BOOTSTRAP_SAMPLES, rng)

    report = results.getvalue()
    report_path = os.path.splitext(CSV_PATH)[0] + '_statistical_analysis.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(report, end='')
    print(f'Results saved to: {report_path}')


if __name__ == '__main__':
    main()
