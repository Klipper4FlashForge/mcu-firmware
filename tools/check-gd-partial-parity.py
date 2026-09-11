#!/usr/bin/env python3
"""Check partial-link sections against canonical isolated candidates, NOT stock.

An unmatched C function must still retain its entire isolated candidate bytes.
Temporary startup/generated ELFs are unavailable: their fresh reports' full-span
SHA256 digests are the reference. Persistent isolated ELFs are re-read as well.
Vectors/veneers are explicit structural exclusions, not independent parity wins.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('motor core gpio serial base protocol stepper trsync irqs adc-irqs '
          'dma-irqs endstop math hardware adc-vendor digital-out angles angle-data '
          'dma-vendor interrupt-control analog-in buttons trig trig-data timer-vendor timer-data '
          'config-finalize pwm-vendor debug-scope debug-scope-data '
          'scatter-handlers '
          'protocol-data scatter-runtime gpio-output memory mpu board runtime '
          'state bss platform-data').split()
SPECIALS = ('mainBoardGD-generated-verification.json', 'mainBoardGD-startup.json',
            'mainBoardGD-ctr.json')
STRUCTURAL = {'vectors', 'linker_veneer'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def path(value):
    candidate = Path(value)
    return candidate if candidate.is_absolute() else ROOT / candidate


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def normalized(row):
    if row.get('evidence_role') == 'semantic_reference':
        return None
    size = row.get('expected_size', row.get('stock_size', row.get('size')))
    actual = row.get('actual_size', row.get('candidate_size'))
    digest = row.get('actual_sha256', row.get('candidate_sha256'))
    if size is None or actual is None or digest is None:
        return None
    return ((row['name'], number(row['address']), number(size)), number(actual), digest)


def freshness(report, stock):
    errors = []
    hashes = report.get('source_sha256', {})
    hashes = dict(hashes) if isinstance(hashes, dict) else {}
    # Older core gates record each compiled source beside its argv, while newer
    # gates carry a dependency map and plain argv lists. Never assume one shape.
    for command in report.get('commands', []):
        if not isinstance(command, dict) or not command.get('source_sha256'):
            continue
        argv = command.get('argv', [])
        if '-c' in argv and argv.index('-c') + 1 < len(argv):
            hashes[argv[argv.index('-c') + 1]] = command['source_sha256']
    if not hashes:
        errors.append('missing source SHA256 map')
    else:
        for name, expected in hashes.items():
            source = path(name)
            if not source.is_file() or sha(source.read_bytes()) != expected:
                errors.append('missing/stale source: ' + name)
    if not report.get('stock_md5') and not report.get('image_sha256'):
        errors.append('missing stock identity')
    if report.get('stock_md5') and hashlib.md5(stock).hexdigest() != report['stock_md5']:
        errors.append('stock MD5 mismatch')
    if report.get('image_sha256') and sha(stock) != report['image_sha256']:
        errors.append('stock SHA256 mismatch')
    if report.get('compiler_sha256'):
        compiler = path(report['compiler'])
        if not compiler.is_file() or sha(compiler.read_bytes()) != report['compiler_sha256']:
            errors.append('missing/stale compiler')
    return errors


def reference_elf(report_path, row):
    """Only known durable artifact conventions; never silently guess a match."""
    label = report_path.parent.name.removeprefix('mainBoardGD-')
    if report_path.name == 'results.json':
        if label == 'state':
            section = ('.alignment_' if row.get('origin') == 'linker_alignment'
                       else '.state_') + row['name']
            return report_path.parent / 'state.elf', section
        if label == 'bss':
            return report_path.parent / 'runtime_state.elf', row['output_section']
        return report_path.parent / (row['name'] + '.elf'), (
            '.rodata' if row.get('kind') == 'constant_data' else '.text')
    if report_path.name == 'mainBoardGD-ctr.json':
        return ROOT / 'work/mainBoardGD-ctr/ctr.elf', '.compile_time_request'
    return None


def read_section(filename, name):
    with filename.open('rb') as stream:
        elf = ELFFile(stream)
        section = elf.get_section_by_name(name)
        if section is None:
            raise ValueError('missing section ' + name)
        return dict(address=section['sh_addr'], size=section['sh_size'],
                    type=section['sh_type'], flags=section['sh_flags'],
                    sha256=sha(section.data()))


def section_agrees(section, address, size, digest):
    return (section['address'] == address and section['size'] == size
            and section['sha256'] == digest)


def self_test():
    digest = sha(b'abc')
    generic = dict(name='x', address=4, expected_size=3, actual_size=3,
                   actual_sha256=digest)
    startup = dict(name='x', address='0x4', stock_size=3, candidate_size=3,
                   actual_sha256=digest)
    motor = dict(name='x', address=4, size=3, actual_size=3, candidate_sha256=digest)
    assert normalized(generic) == normalized(startup) == normalized(motor)
    assert normalized(dict(name='x', address=4, size=3)) is None
    assert normalized(dict(generic, evidence_role='semantic_reference')) is None
    altered = dict(generic, actual_sha256=sha(b'abd'))
    assert normalized(altered) != normalized(generic)
    assert freshness({}, b'') == ['missing source SHA256 map', 'missing stock identity']
    assert freshness({'commands': [['compiler', '-c', 'source.c']]}, b'') == freshness({}, b'')
    source = str(Path(__file__).resolve())
    old = dict(commands=[dict(argv=['cc', '-c', source], source_sha256=sha(Path(source).read_bytes()))],
               stock_md5=hashlib.md5(b'').hexdigest())
    assert not freshness(old, b'')
    old['commands'][0]['source_sha256'] = '0' * 64
    assert freshness(old, b'') == ['missing/stale source: ' + source]
    section = dict(address=4, size=3, sha256=digest)
    assert section_agrees(section, 4, 3, digest)
    for address, size, candidate_digest in [(8, 3, digest), (4, 4, digest), (4, 3, sha(b'abd'))]:
        assert not section_agrees(section, address, size, candidate_digest)
    assert sha(bytes(4)) != sha(bytes(3))
    print('parity schema, missing evidence, changed byte and extent self-tests passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial-report', type=Path,
                        default=ROOT / 'work/mainBoardGD-partial/results.json')
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'work/mainBoardGD-partial-parity.json')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    stock = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    partial_path = args.partial_report.resolve()
    partial = json.loads(partial_path.read_text())
    errors = freshness(partial, stock)
    linked = path(partial['linked_elf'])
    if not linked.is_file() or sha(linked.read_bytes()) != partial.get('linked_elf_sha256'):
        errors.append('partial linked ELF missing/stale SHA256')
    with linked.open('rb') as stream:
        allocated = {s.name for s in ELFFile(stream).iter_sections()
                     if s['sh_flags'] & 2 and s['sh_size']}
    declared = [row['output_section'] for row in partial['results']]
    if len(set(declared)) != len(declared):
        errors.append('duplicate partial section declarations')
    if allocated != set(declared):
        errors.append('allocated/declaration section mismatch: ' + repr(sorted(allocated ^ set(declared))))
    references, provenance = {}, []
    reports = [ROOT / ('work/mainBoardGD-' + label + '/results.json') for label in LABELS]
    reports += [ROOT / 'work' / name for name in SPECIALS]
    for filename in reports:
        if not filename.exists():
            continue  # Required missing references are recorded individually below.
        report = json.loads(filename.read_text())
        stale = freshness(report, stock)
        provenance.append(dict(path=str(filename), sha256=sha(filename.read_bytes()), errors=stale,
            semantic_reference_rows=[row['name'] for row in report.get('results', [])
                                     if row.get('evidence_role') == 'semantic_reference']))
        for row in report.get('results', report.get('functions', [])):
            norm = normalized(row)
            if norm is None:
                continue
            key, size, digest = norm
            references.setdefault(key, []).append((filename, row, report, stale, size, digest))
    results = []
    for row in partial['results']:
        issues = []
        observed = read_section(linked, row['output_section'])
        if not section_agrees(observed, row['address'], row['actual_size'], row['actual_sha256']):
            issues.append('partial section disagrees with its report')
        result = dict(name=row['name'], kind=row['kind'], address=row['address'],
                      size=row['actual_size'], output_section=row['output_section'],
                      actual_sha256=observed['sha256'], references=[], errors=issues)
        if row['kind'] in STRUCTURAL:
            result['status'] = 'error' if issues else 'structural_exclusion'
            result['reason'] = 'synthesized layout has no independent isolated candidate'
            results.append(result)
            continue
        matches = references.get((row['name'], row['address'], row['size']), [])
        if not matches:
            issues.append('missing canonical full-section reference')
        for filename, reference, report, stale, size, digest in matches:
            evidence = dict(report=str(filename), candidate_sha256=digest, candidate_size=size)
            result['references'].append(evidence)
            if stale:
                issues.append('stale reference: ' + str(filename))
            if size != observed['size'] or digest != observed['sha256']:
                issues.append('isolated candidate bytes/extent differ: ' + str(filename))
            candidate = reference_elf(filename, reference)
            if candidate:
                candidate_path, section = candidate
                evidence['elf'] = str(candidate_path)
                if not candidate_path.is_file():
                    issues.append('missing persistent isolated ELF: ' + str(candidate_path))
                else:
                    isolated = read_section(candidate_path, section)
                    evidence['elf_sha256'] = sha(candidate_path.read_bytes())
                    if not section_agrees(isolated, row['address'], size, digest):
                        issues.append('isolated ELF differs from reference report: ' + str(candidate_path))
            else:
                evidence['evidence_mode'] = 'fresh full-span digest; temporary ELF not retained'
            if row['kind'] == 'zero_initialized_data':
                region = report.get('zero_region', {})
                start, count = region.get('address', 0), region.get('size', 0)
                if not (observed['type'] == 'SHT_NOBITS'
                        and start <= row['address'] < row['address'] + observed['size'] <= start + count
                        and observed['sha256'] == sha(bytes(observed['size']))):
                    issues.append('ZI requires NOBITS storage in explicit proven zero region')
        result['status'] = 'error' if issues else 'parity'
        results.append(result)
    counts = Counter(row['status'] for row in results)
    categories = {}
    for row in results:
        category = categories.setdefault(row['kind'], dict(sections=0, bytes=0, parity=0, errors=0))
        category['sections'] += 1
        category['bytes'] += row['size']
        category['parity'] += row['status'] == 'parity'
        category['errors'] += row['status'] == 'error'
    passed = not errors and not counts['error']
    report = dict(schema_version=1, scope='partial versus canonical isolated candidate parity; not stock equality',
                  passed=passed, whole_image_verified=False, partial_report=str(partial_path),
                  partial_report_sha256=sha(partial_path.read_bytes()), linked_elf=str(linked),
                  linked_elf_sha256=sha(linked.read_bytes()), stock_sha256=sha(stock),
                  checker_sha256=sha(Path(__file__).read_bytes()), errors=errors,
                  reference_reports=provenance, counts=dict(counts), categories=categories,
                  freshness_scope='Only dependencies recorded by each producing gate can be checked; '
                                  'older core/startup reports have narrower dependency manifests.',
                  results=results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(f"{counts['parity']} parity, {counts['error']} failed/missing, "
          f"{counts['structural_exclusion']} explicit structural exclusions")
    for row in results:
        for error in row['errors']:
            print(row['name'] + ': ' + error)
    for error in errors:
        print(error)
    print('Report: ' + str(args.out))
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
