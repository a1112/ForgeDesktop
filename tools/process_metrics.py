"""Read-only Linux process metrics; no command-line arguments or secrets recorded."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time


def parse_stat(value):
    left, right = value.index('('), value.rindex(')')
    fields = value[right + 1:].split()
    return {'pid': int(value[:left]), 'name': value[left + 1:right],
            'ppid': int(fields[1]), 'ticks': int(fields[11]) + int(fields[12]),
            'start': int(fields[19])}


def parse_pss(value):
    for line in value.splitlines():
        if line.startswith('Pss:'):
            return int(line.split()[1])
    return None


def cpu_percent(before, after, ticks_per_second, seconds):
    if seconds <= 0 or ticks_per_second <= 0:
        raise ValueError('sampling interval and clock frequency must be positive')
    delta = sum(max(0, row['ticks'] - before[pid]['ticks'])
                for pid, row in after.items()
                if pid in before and before[pid]['start'] == row['start'])
    return delta / ticks_per_second / seconds * 100


def select_group(table, names, uid):
    selected = {pid for pid, row in table.items()
                if row['uid'] == uid and row['name'] in names}
    while True:
        children = {pid for pid, row in table.items()
                    if row['uid'] == uid and row['ppid'] in selected}
        if children <= selected:
            return selected
        selected |= children


def read_processes(root):
    table = {}
    for path in root.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            row = parse_stat((path / 'stat').read_text())
            row['uid'] = path.stat().st_uid
            # stat's comm is truncated; executable basename is safe to record.
            try:
                row['name'] = Path(os.readlink(path / 'exe')).name
            except OSError:
                pass
            table[row['pid']] = row
        except (OSError, ValueError, IndexError):
            continue  # Processes may disappear between directory and stat reads.
    return table


def sample(groups, duration, interval, uid):
    proc = Path('/proc')
    frequency = os.sysconf('SC_CLK_TCK')
    samples = []
    start = time.monotonic()
    while True:
        stamp = time.monotonic()
        table = read_processes(proc)
        current = {'seconds': stamp - start, 'groups': {}}
        for label, names in groups.items():
            selected = select_group(table, names, uid)
            rows = {}
            for pid in sorted(selected):
                row = dict(table[pid])
                try:
                    row['pss_kib'] = parse_pss((proc / str(pid) / 'smaps_rollup').read_text())
                except OSError:
                    row['pss_kib'] = None
                rows[pid] = row
            current['groups'][label] = rows
        samples.append(current)
        if stamp - start >= duration:
            break
        time.sleep(min(interval, max(0, duration - (time.monotonic() - start))))
    summaries = {}
    elapsed = samples[-1]['seconds']
    for label in groups:
        cpu_seconds = 0
        pss = []
        identities = []
        incomplete_pss = False
        for index, point in enumerate(samples):
            rows = point['groups'][label]
            identities.append({(pid, row['start']) for pid, row in rows.items()})
            if not rows or any(row['pss_kib'] is None for row in rows.values()):
                incomplete_pss = True
            else:
                pss.append(sum(row['pss_kib'] for row in rows.values()))
            if index:
                seconds = point['seconds'] - samples[index - 1]['seconds']
                cpu_seconds += cpu_percent(samples[index - 1]['groups'][label], rows,
                                           frequency, seconds) * seconds / 100
        stable = all(value == identities[0] for value in identities) and bool(identities[0])
        summaries[label] = {'stable_process_set': stable,
                            'complete_pss': not incomplete_pss,
                            'cpu_percent_one_core': cpu_seconds / elapsed * 100,
                            'pss_mib_mean': statistics.mean(pss) / 1024 if pss else None,
                            'pss_mib_max': max(pss) / 1024 if pss else None}
    return {'schemaVersion': 1, 'duration_seconds': elapsed, 'uid': uid,
            'clock_ticks_per_second': frequency, 'summary': summaries,
            'samples': samples,
            'limitations': ['CPU comparison is valid only for stable process sets.',
                            'No frame time, input latency or noVNC latency is inferred.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', action='append', required=True, help='label=executable,executable')
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--interval', type=float, default=1)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 28800 or not .1 <= args.interval <= 60:
        parser.error('seconds must be 1..28800 and interval .1..60')
    groups = {}
    for item in args.group:
        label, separator, names = item.partition('=')
        if not separator or not label or not names or label in groups:
            parser.error('groups need unique labels and executable names')
        groups[label] = set(names.split(','))
    print(json.dumps(sample(groups, args.seconds, args.interval, os.getuid()), indent=2))


if __name__ == '__main__':
    main()
