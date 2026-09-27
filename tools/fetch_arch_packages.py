"""Fetch a snapshot package closure by bounded ranges, verify digests, retain signatures.

Package installation MUST also verify these signatures against the pinned Arch
keyring. Repository metadata alone is not a trust root. No packages are executed.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

SNAPSHOT = '2026/08/01'
CHUNK = 1024 * 1024


def archive_filename(url):
    match = re.fullmatch(r'https://archive\.archlinux\.org/repos/2026/08/01/'
                         r'(?:core|extra)/os/x86_64/([A-Za-z0-9_+:.@-]+\.pkg\.tar\.zst)', url)
    if not match:
        raise ValueError('URL outside pinned Arch package snapshot')
    return match[1]


def valid_file(path, size, digest):
    if not path.is_file() or path.is_symlink() or path.stat().st_size != size:
        return False
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            hasher.update(block)
    return hasher.hexdigest() == digest


def metadata(directory):
    result = {}
    for repository in ('core', 'extra'):
        with tarfile.open(directory / (repository + '.db')) as archive:
            for item in archive:
                if not item.isfile() or not item.name.endswith('/desc'):
                    continue
                if item.size > 1024 * 1024:
                    raise ValueError('repository descriptor too large')
                fields, key = {}, None
                for line in archive.extractfile(item).read().decode().splitlines():
                    if line.startswith('%') and line.endswith('%'):
                        key = line[1:-1]
                        fields[key] = []
                    elif line and key:
                        fields[key].append(line)
                result[fields['FILENAME'][0]] = fields
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--urls', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    meta = metadata(args.db)
    packages, jobs = [], []
    for url in args.urls.read_text().splitlines():
        name = archive_filename(url)
        fields = meta[name]
        size = int(fields['CSIZE'][0])
        if not 0 < size <= 1024 ** 3:
            raise ValueError('package size outside bound')
        signature = base64.b64decode(fields['PGPSIG'][0], validate=True)
        target = args.output / name
        (args.output / (name + '.sig')).write_bytes(signature)
        package = dict(name=fields['NAME'][0], version=fields['VERSION'][0], filename=name,
                       size=size, sha256=fields['SHA256SUM'][0], url=url,
                       signatureSha256=hashlib.sha256(signature).hexdigest(), licenses=fields['LICENSE'])
        packages.append(package)
        if valid_file(target, size, package['sha256']):
            continue
        for start in range(0, size, CHUNK):
            jobs.append((url, target, start, min(start + CHUNK, size) - 1))

    def fetch(job):
        url, target, start, end = job
        part = target.with_name(target.name + '.part-' + str(start))
        # Incomplete ranges are never resumed as though verified package bytes.
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--retry', '3',
                        '--connect-timeout', '10', '--max-time', '180', '--range',
                        f'{start}-{end}', '--output', str(part), url], check=True)
        if part.stat().st_size != end - start + 1:
            raise ValueError('server did not return exact requested range')

    with ThreadPoolExecutor(max_workers=16) as workers:
        for index, _ in enumerate(workers.map(fetch, jobs), 1):
            if index % 16 == 0:
                print(f'ranges {index}/{len(jobs)}', flush=True)
    for package in packages:
        target = args.output / package['filename']
        if not valid_file(target, package['size'], package['sha256']):
            partial = target.with_name(target.name + '.assembling')
            with partial.open('wb') as output:
                for start in range(0, package['size'], CHUNK):
                    output.write(target.with_name(target.name + '.part-' + str(start)).read_bytes())
            if not valid_file(partial, package['size'], package['sha256']):
                raise ValueError('downloaded package digest mismatch: ' + target.name)
            partial.replace(target)
        for start in range(0, package['size'], CHUNK):
            target.with_name(target.name + '.part-' + str(start)).unlink(missing_ok=True)
    (args.output / 'packages.json').write_text(json.dumps(dict(schemaVersion=1,
        snapshot=SNAPSHOT, packages=packages), indent=2) + '\n')
    print(f'digest-verified {len(packages)} packages; signature verification required at install', flush=True)


if __name__ == '__main__':
    main()
