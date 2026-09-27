#!/usr/bin/env python3
"""Summarize measured records without treating missing evidence as a pass.

Output is observational, not final acceptance: fixed VM resources, workload,
warm-up, foreground browser and visual ROI validity need independent evidence.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def distribution(values):
    require(bool(values) and all(finite(v) for v in values), 'timings must be finite nonnegative samples')
    ordered = sorted(values)
    return dict(count=len(values), mean_ms=statistics.mean(values),
                p50_ms=ordered[math.ceil(len(values)*.5)-1],
                p95_ms=ordered[math.ceil(len(values)*.95)-1], max_ms=ordered[-1])


def optional_distribution(values):
    return distribution(values) if values else None


def frames(text):
    reader = csv.DictReader(io.StringIO(text))
    require(reader.fieldnames == ['kind','elapsed_us','damaged'], 'unsupported frame CSV schema')
    damaged, undamaged = [], []
    for index, row in enumerate(reader):
        require(index < 100000 and set(row) == {'kind','elapsed_us','damaged'}
                and row['kind'] == 'frame' and row['damaged'] in ('0','1')
                and re.fullmatch(r'[0-9]{1,16}', row['elapsed_us'] or ''), 'invalid frame row')
        (damaged if row['damaged'] == '1' else undamaged).append(int(row['elapsed_us'])/1000)
    return dict(damaged_frames=optional_distribution(damaged),
                undamaged_attempts=optional_distribution(undamaged),
                enough_samples_for_gate=len(damaged) >= 120,
                scope='dirty render through submission; excludes vblank/scanout/noVNC')


def launcher(text):
    results = {}
    for label, marker in [('qt_submission','launcher-submit-us'),
                          ('compositor_submission','launcher-compositor-submit-us')]:
        values = [int(value)/1000 for value in re.findall(
            r'^ForgeDesktop ' + marker + r'=([0-9]{1,16})$', text, re.MULTILINE)]
        require(len(values) <= 10000, 'launcher trace exceeds sample bound')
        results[label] = optional_distribution(values)
    results['enough_samples_for_gate'] = all(results[key] and results[key]['count'] >= 30
        for key in ('qt_submission','compositor_submission'))
    results['scope'] = 'QML handler to submission; excludes pre-handler dispatch and physical presentation'
    return results


def processes(capture):
    require(type(capture.get('schemaVersion')) is int and capture['schemaVersion'] == 1,
            'unsupported process metrics schema')
    value = capture.get('summary', {}).get('desktop', {})
    selection = capture.get('selection', {}).get('desktop', {})
    qualified = (finite(capture.get('duration_seconds'))
        and capture['duration_seconds'] >= 60
        and selection.get('descendants') is False
        and set(selection.get('names', [])) == {'forge-compositor','forge-shell'}
        and value.get('stable_process_set') is True and value.get('complete_pss') is True
        and all(finite(value.get(key)) for key in ('cpu_percent_one_core','pss_mib_mean','pss_mib_max')))
    return dict(qualified=qualified, duration_seconds=capture.get('duration_seconds'),
                observed=value, scope='exact compositor and shell executables; excludes launched applications')


def novnc(capture):
    require(type(capture.get('schemaVersion')) is int and capture['schemaVersion'] == 1 and
        capture.get('metric') == 'pointer-down-to-first-roi-pixel-change', 'unsupported noVNC metric')
    rows = capture.get('observations')
    require(type(rows) is list and len(rows) <= 100, 'invalid noVNC observations')
    values, failures, cases = [], Counter(), set()
    for row in rows:
        require(type(row) is dict and type(row.get('case')) is str and finite(row.get('elapsedMs'))
            and row.get('outcome') in ('changed','timeout','disconnected','canvas-resized'), 'invalid noVNC row')
        cases.add(row['case'])
        if row['outcome'] == 'changed':
            values.append(row['elapsedMs'])
        else:
            failures[row['outcome']] += 1
    return dict(first_visible_change=optional_distribution(values), failures=dict(failures),
                cases=sorted(cases), enough_valid_samples=len(values) >= 30 and not failures and len(cases) == 1,
                scope='browser input through first changed ROI pixels; rAF quantized, not content-complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('processes','frames','launcher','novnc'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    require(any(vars(args).values()), 'provide at least one measurement input')
    report = {'schemaVersion':1, 'qualification':'observations only; fixed conditions/workload/visual validation required',
              'missing':[], 'sources':{}}
    for name, parse in [('processes',processes), ('frames',frames), ('launcher',launcher), ('novnc',novnc)]:
        path = getattr(args,name)
        if path is None:
            report['missing'].append(name)
            continue
        require(path.stat().st_size <= 16*1024*1024, 'measurement file too large')
        with path.open('rb') as stream:
            data = stream.read(16*1024*1024+1)
        require(len(data) <= 16*1024*1024, 'measurement file grew past limit')
        text = data.decode('utf-8')
        report['sources'][name] = dict(file=path.name, sha256=hashlib.sha256(data).hexdigest())
        report[name] = parse(json.loads(text) if name in ('processes','novnc') else text)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
