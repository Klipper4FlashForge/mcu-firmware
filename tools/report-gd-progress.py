#!/usr/bin/env python3
"""Inventory mainBoardGD source checks without double-counting address ranges.

    python3 tools/report-gd-progress.py --out work/mainBoardGD-progress.json
    python3 tools/report-gd-progress.py --gate motor=work/another/results.json

Reads canonical reports only, never chooses the best experimental result.
Missing/stale checks are visible. Full function spans include literal pools:
this report does not infer instruction bytes or a whole-firmware match.
Generated source manifests alone do not prove a successful compile/data gate.
Architectural assembly is separate from C. Typed zero-initialized storage is
checked only against the explicit stock scatter zero-fill region and is never
included in executable, initialized-data, or legacy total-union byte counts.
"""
import argparse
import hashlib
import json
from pathlib import Path
from scatterload import decompress, entries, HELPERS


ROOT = Path(__file__).resolve().parents[1]
RECOVERED = ROOT / 'mcu/mainBoardGD/recovered'
STOCK = ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin'
MD5 = 'fb64911bac422a27d7ed7fab3597603f'
REGIONS = {'itcm': (0, 28120), 'flash': (0x08000000, 0x08003778),
           'initialized_ram': (0x24000000, 0x24002e88),
           'zero_initialized_ram': (0x24002e88, 0x2400b340)}
C_KINDS = ('function_span_code_and_pool', 'executable_code')
ASM_KIND = 'assembly_span_code_and_pool'
ZERO_KIND = 'zero_initialized_data'
DATA_KINDS = ('generated_data', 'literal_pool', 'initialized_data', 'constant_data')
DEFAULTS = {
    'toolchain': ROOT / 'work/mainBoardGD-toolchain.json',
    'motor': ROOT / 'work/mainBoardGD-motor/results.json',
    'core': ROOT / 'work/mainBoardGD-core/results.json',
    'gpio': ROOT / 'work/mainBoardGD-gpio/results.json',
    'startup': ROOT / 'work/mainBoardGD-startup.json',
    'generated': ROOT / 'work/mainBoardGD-generated-verification.json',
    'serial': ROOT / 'work/mainBoardGD-serial/results.json',
    'base': ROOT / 'work/mainBoardGD-base/results.json',
    'protocol': ROOT / 'work/mainBoardGD-protocol/results.json',
    'state': ROOT / 'work/mainBoardGD-state/results.json',
    'retained_ctr': ROOT / 'work/mainBoardGD-ctr.json',
    'runtime': ROOT / 'work/mainBoardGD-runtime/results.json',
    'scatter_handlers': ROOT / 'work/mainBoardGD-scatter-handlers/results.json',
    'bss': ROOT / 'work/mainBoardGD-bss/results.json',
    'stepper': ROOT / 'work/mainBoardGD-stepper/results.json',
    'mpu': ROOT / 'work/mainBoardGD-mpu/results.json',
    'board': ROOT / 'work/mainBoardGD-board/results.json',
    'trsync': ROOT / 'work/mainBoardGD-trsync/results.json',
    'gpio_output': ROOT / 'work/mainBoardGD-gpio-output/results.json',
    'memory': ROOT / 'work/mainBoardGD-memory/results.json',
    'irqs': ROOT / 'work/mainBoardGD-irqs/results.json',
    'adc_irqs': ROOT / 'work/mainBoardGD-adc-irqs/results.json',
    'dma_irqs': ROOT / 'work/mainBoardGD-dma-irqs/results.json',
    'endstop': ROOT / 'work/mainBoardGD-endstop/results.json',
    'math': ROOT / 'work/mainBoardGD-math/results.json',
    'hardware': ROOT / 'work/mainBoardGD-hardware/results.json',
    'adc_vendor': ROOT / 'work/mainBoardGD-adc-vendor/results.json',
    'digital_out': ROOT / 'work/mainBoardGD-digital-out/results.json',
    'angles': ROOT / 'work/mainBoardGD-angles/results.json',
    'angle_data': ROOT / 'work/mainBoardGD-angle-data/results.json',
    'dma_vendor': ROOT / 'work/mainBoardGD-dma-vendor/results.json',
    'interrupt_control': ROOT / 'work/mainBoardGD-interrupt-control/results.json',
    'analog_in': ROOT / 'work/mainBoardGD-analog-in/results.json',
    'buttons': ROOT / 'work/mainBoardGD-buttons/results.json',
    'trig': ROOT / 'work/mainBoardGD-trig/results.json',
    'trig_data': ROOT / 'work/mainBoardGD-trig-data/results.json',
    'timer_vendor': ROOT / 'work/mainBoardGD-timer-vendor/results.json',
    'timer_data': ROOT / 'work/mainBoardGD-timer-data/results.json',
    'config_finalize': ROOT / 'work/mainBoardGD-config-finalize/results.json',
    'pwm_vendor': ROOT / 'work/mainBoardGD-pwm-vendor/results.json',
    'debug_scope': ROOT / 'work/mainBoardGD-debug-scope/results.json',
    'debug_scope_data': ROOT / 'work/mainBoardGD-debug-scope-data/results.json',
    'protocol_data': ROOT / 'work/mainBoardGD-protocol-data/results.json',
    'platform_data': ROOT / 'work/mainBoardGD-platform-data/results.json',
    'scatter_runtime': ROOT / 'work/mainBoardGD-scatter-runtime/results.json',
}
SOURCES = {
    'toolchain': ['toolchain-probes.c'],
    'motor': ['mclib_commands.c', 'mclib_state.h'],
    'core': ['core.c', 'ff_commands.c'],
    'gpio': ['gpio.c', 'gpio.h'],
    'startup': ['system_init.c', 'nvic.c'],
    'serial': ['serial.c', 'serial_irq.c', 'serial_vendor.c', 'serial.h'],
    'base': ['base_commands.c', 'debug_commands.c', 'command_pointer.c',
             'oid_commands.c', 'scheduler_helpers.c', 'scheduler_timers.c',
             'scheduler_add.c', 'scheduler_main.c', 'statistics.c',
             'move_queue.c', 'move_queue.h', 'scheduler_shutdown.c', 'memory_bounds.c'],
    'protocol': ['command_protocol.c', 'command_protocol.h'],
    'state': ['state.c', 'state.h', 'mclib_state.h', 'gpio.h'],
    'retained_ctr': ['compile_time_requests.c'],
    'runtime': ['startup_runtime.S'],
    'scatter_handlers': ['scatter_handlers.S'],
    'bss': ['runtime_state.c', 'runtime_state.h'],
    'stepper': ['stepper.c'],
    'mpu': ['mpu.c', 'mpu.h'],
    'board': ['board_main.c'],
    'trsync': ['trsync.c', 'trsync.h', 'stepper.h'],
    'gpio_output': ['gpio_output.c', 'gpio.h', 'mclib_state.h'],
    'memory': ['runtime_memory.c', 'runtime_memory.h'],
    'irqs': ['motor_irqs.c', 'timer_dispatch.c', 'mclib_state.h'],
    'adc_irqs': ['adc_interrupts.c'],
    'dma_irqs': ['dma_interrupts.c'],
    'endstop': ['endstop.c', 'endstop.h'],
    'math': ['mclib_math.c', 'mclib_state.h'],
    'hardware': ['mclib_hardware.c', 'mclib_hardware.h', 'mclib_state.h'],
    'adc_vendor': ['adc_vendor.c'],
    'digital_out': ['digital_out.c', 'digital_out.h'],
    'angles': ['mclib_angles.c', 'mclib_state.h'],
    'angle_data': ['mclib_angles.c'],
    'dma_vendor': ['dma_vendor.c', 'mclib_hardware.h'],
    'interrupt_control': ['interrupt_control.c', 'mclib_hardware.h'],
    'analog_in': ['analog_in.c', 'analog_in.h'],
    'buttons': ['buttons.c', 'buttons.h'],
    'trig': ['mclib_trig.c'],
    'trig_data': ['mclib_trig.c'],
    'timer_vendor': ['timer_vendor.c', 'mclib_hardware.h'],
    'timer_data': ['timer_vendor.c'],
    'config_finalize': ['config_finalize.c', 'move_queue.h'],
    'pwm_vendor': ['mclib_pwm_vendor.c', 'mclib_hardware.h'],
    'debug_scope': ['debug_scope.c', 'debug_scope.h'],
    'debug_scope_data': ['debug_scope.c', 'debug_scope.h'],
    'protocol_data': ['protocol_data.c', 'command_protocol.h'],
    'platform_data': ['clock_tables.c'],
    'scatter_runtime': ['runtime_scatter.c'],
    'generated': ['generated/generated.c', 'generated/generated.h',
                  'generated/lookup-match.c', 'generated/verify-combined.ld'],
}


def intervals(points):
    """A disjoint, sorted, half-open interval representation of byte addresses."""
    result = []
    for point in sorted(points):
        if result and result[-1]['end'] == point:
            result[-1]['end'] += 1
            result[-1]['size'] += 1
        else:
            result.append({'start': point, 'end': point + 1, 'size': 1})
    return result


def locations(value):
    return set(range(value['address'], value['address'] + value['size']))


def resolve_source(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def freshness(name, path, payload):
    """Use recorded hashes when available, otherwise only flag newer sources."""
    hashes = {}
    if isinstance(payload, dict):
        if isinstance(payload.get('source_sha256'), dict):
            hashes.update({resolve_source(source): digest
                           for source, digest in payload['source_sha256'].items()})
        elif payload.get('source') and payload.get('source_sha256'):
            hashes[resolve_source(payload['source'])] = payload['source_sha256']
        for command in payload.get('commands', []):
            # Newer reports keep raw argv arrays here and put all dependency
            # hashes in source_sha256; older core reports attach a hash per argv.
            if isinstance(command, list):
                continue
            if not isinstance(command, dict):
                raise ValueError('command metadata must be an argv list or object')
            argv = command.get('argv', [])
            if '-c' in argv and command.get('source_sha256'):
                hashes[resolve_source(argv[argv.index('-c') + 1])] = command['source_sha256']
        for source in payload.get('sources', []):
            if source.get('path') and source.get('sha256'):
                hashes[resolve_source(source['path'])] = source['sha256']
    candidates = set(hashes) | {RECOVERED / source for source in SOURCES.get(name, [])}
    checks, stale = [], False
    for source in sorted(candidates):
        if not source.is_file():
            status = 'source_missing'
        elif source in hashes:
            status = ('hash_matches' if hashlib.sha256(source.read_bytes()).hexdigest()
                      == hashes[source] else 'hash_mismatch')
        else:
            status = ('source_newer_than_report' if source.stat().st_mtime_ns
                      > path.stat().st_mtime_ns else 'mtime_only_not_content_pinned')
        stale |= status in ('source_missing', 'hash_mismatch', 'source_newer_than_report')
        checks.append({'path': str(source), 'status': status})
    return {'stale': stale, 'sources': checks,
            'limitation': 'Only listed source inputs are checked; absent header/compiler hashes are not inferred.'}


def stock_zero_region(stock):
    """Prove zero-fill from the stock scatter record and identified helper."""
    found = []
    for _, address, size, helper in entries(stock, 0x08000000, 0x3744):
        offset = helper - 0x08000000
        if HELPERS.get(stock[offset:offset + 8]) == 'zeroinit':
            found.append(dict(address=address, size=size, helper=helper))
    start, end = REGIONS['zero_initialized_ram']
    if len(found) != 1 or (found[0]['address'], found[0]['size']) != (start, end - start):
        raise ValueError('stock scatter zero-fill region differs from profile')
    return found[0]


def normal_row(row, gate, state, stock=None, ram=None, zero_region=None):
    address = row.get('address', row.get('stock_address'))
    size = row.get('expected_size', row.get('stock_size', row.get('size')))
    if not isinstance(address, int) or not isinstance(size, int) or size <= 0:
        raise ValueError('invalid address/size in ' + gate + ': ' + repr(row.get('name')))
    if not any(start <= address and address + size <= end for start, end in REGIONS.values()):
        raise ValueError('range outside stock address regions: ' + repr(row.get('name')))
    kind = row.get('kind', 'function_span_code_and_pool')
    # Older runtime reports used the generic function kind. This gate compiles
    # architectural assembly, never C, regardless of its legacy row spelling.
    if gate == 'runtime' or kind == 'runtime_assembly':
        kind = ASM_KIND
    elif kind == 'function':
        kind = 'function_span_code_and_pool'
    if kind not in C_KINDS + DATA_KINDS + (ASM_KIND, ZERO_KIND):
        raise ValueError('unsupported range kind: ' + str(kind))
    zi_start, zi_end = REGIONS['zero_initialized_ram']
    in_zero_region = zi_start <= address and address + size <= zi_end
    if (kind == ZERO_KIND) != in_zero_region:
        raise ValueError('zero-initialized storage must have a separate range kind')
    if kind in C_KINDS + (ASM_KIND,) and address >= 0x24000000:
        raise ValueError('RAM data profile cannot be counted as executable source')
    if kind == ZERO_KIND:
        if zero_region is None or not (zero_region['address'] <= address and
                address + size <= zero_region['address'] + zero_region['size']):
            raise ValueError('zero-byte verification requires an explicit stock-proven zero region')
        if not row.get('expected_sha256'):
            raise ValueError('zero-initialized row requires an expected byte hash')
    exact = row.get('exact', row.get('byte_exact'))
    candidate_size = row.get('actual_size', row.get('candidate_size'))
    matched = row.get('matching_bytes', row.get('matched_bytes', row.get('same_position_bytes')))
    if exact is True and ((candidate_size is not None and candidate_size != size)
                          or (matched is not None and matched != size)):
        raise ValueError('exact verdict contradicts measured size/bytes: ' + repr(row.get('name')))
    if stock is not None and row.get('expected_sha256'):
        if kind == ZERO_KIND:
            expected = bytes(size)
        elif address >= 0x24000000:
            if ram is None:
                raise ValueError('initialized RAM hash check requires expanded region')
            offset = address - 0x24000000
            expected = ram[offset:offset + size]
        else:
            offset = address + 0x4418 if address < 0x08000000 else address - 0x08000000
            expected = stock[offset:offset + size]
        if len(expected) != size:
            raise ValueError('expected byte interval is truncated')
        expected_sha = hashlib.sha256(expected).hexdigest()
        if row['expected_sha256'] != expected_sha:
            raise ValueError('expected byte hash differs from stock: ' + repr(row.get('name')))
        candidate_sha = row.get('actual_sha256', row.get('candidate_sha256'))
        if exact is True and candidate_sha not in (None, expected_sha):
            raise ValueError('exact verdict contradicts candidate hash: ' + repr(row.get('name')))
    code_end = row.get('code_end')
    if code_end is not None and not address <= code_end <= address + size:
        raise ValueError('code/pool boundary outside span: ' + repr(row.get('name')))
    status = 'stale' if state['stale'] else 'exact' if exact is True else 'unmatched' if exact is False else 'unchecked'
    evidence_role = row.get('evidence_role', 'primary')
    if evidence_role not in ('primary', 'semantic_reference'):
        raise ValueError('unknown evidence role: ' + str(evidence_role))
    return {'gate': gate, 'name': row.get('name', 'unnamed'), 'address': address,
            'size': size, 'kind': kind, 'origin': row.get('origin'),
            'evidence_role': evidence_role,
            'status': status, 'reported_exact': exact,
            'code_end': row.get('code_end'), 'pool_end': row.get('pool_end')}


def inventory(records):
    """Union all evidence, with conflicts neither silently won nor summed."""
    # C explanations of proven assembly-origin handlers are retained and
    # tested, but are not a second active owner or a source-equality claim.
    records = [row for row in records if row.get('evidence_role') != 'semantic_reference']
    summaries, duplicates, conflicts = {}, [], []
    for index, first in enumerate(records):
        for second in records[index + 1:]:
            start = max(first['address'], second['address'])
            end = min(first['address'] + first['size'], second['address'] + second['size'])
            if start >= end:
                continue
            pair = {'start': start, 'end': end, 'size': end - start,
                    'first': first['gate'] + ':' + first['name'],
                    'second': second['gate'] + ':' + second['name']}
            first_func = first['kind'] in C_KINDS + (ASM_KIND,)
            second_func = second['kind'] in C_KINDS + (ASM_KIND,)
            if first_func and second_func:
                same = (first['address'], first['size']) == (second['address'], second['size'])
                different_language = (first['kind'] == ASM_KIND) != (second['kind'] == ASM_KIND)
                if different_language or not same or {first['status'], second['status']} == {'exact', 'unmatched'}:
                    pair['reason'] = ('overlapping C and assembly ownership' if different_language else
                                      'different overlapping function bounds' if not same else
                                      'exact/unmatched verdicts disagree')
                    conflicts.append(pair)
                else:
                    duplicates.append(pair)
            elif not first_func and not second_func and {first['status'], second['status']} == {'exact', 'unmatched'}:
                pair['reason'] = 'overlapping data verdicts disagree'
                conflicts.append(pair)
    conflict_bytes = set().union(*(set(range(c['start'], c['end'])) for c in conflicts))
    for region, (start, end) in REGIONS.items():
        universe = set(range(start, end))
        exact_func, unmatched_func, stale, exact_data, data, code = (set() for _ in range(6))
        exact_asm, unmatched_asm, assembly, exact_zero, unmatched_zero, zero = (set() for _ in range(6))
        generated, exact_generated, exact_pools = (set() for _ in range(3))
        covered = set()
        for row in records:
            points = locations(row) & universe
            covered |= points
            is_data = row['kind'] in DATA_KINDS
            if is_data:
                data |= points
                if row['kind'] == 'generated_data':
                    generated |= points
                if row['status'] == 'exact':
                    exact_data |= points
                    if row['kind'] == 'generated_data':
                        exact_generated |= points
                    elif row['kind'] == 'literal_pool':
                        exact_pools |= points
            elif row['kind'] == ASM_KIND:
                assembly |= points
                if row['status'] == 'exact':
                    exact_asm |= points
                elif row['status'] == 'unmatched':
                    unmatched_asm |= points
            elif row['kind'] == ZERO_KIND:
                zero |= points
                if row['status'] == 'exact':
                    exact_zero |= points
                elif row['status'] == 'unmatched':
                    unmatched_zero |= points
            elif row['status'] == 'exact':
                exact_func |= points
                if row['kind'] == 'executable_code':
                    code |= points
                elif row.get('code_end') is not None:
                    code |= points & set(range(row['address'], row['code_end']))
            elif row['status'] == 'unmatched':
                unmatched_func |= points
            if row['status'] == 'stale':
                stale |= points
        local_conflict = conflict_bytes & universe
        exact_func -= local_conflict
        exact_data -= local_conflict
        exact_asm -= local_conflict
        exact_zero -= local_conflict
        exact = exact_func | exact_data | exact_asm | exact_zero
        unmatched = unmatched_func | unmatched_asm | unmatched_zero
        # These counters are exclusive and sum to the region's denominator.
        # Full function-span totals below remain explicitly code-plus-pool.
        partitions = {
            'exact_data_and_literal_pools': exact_data,
            'exact_function_spans_excluding_exact_data': exact_func - exact_data,
            'exact_assembly_spans_excluding_exact_data': exact_asm - exact_data,
            'exact_zero_initialized_data': exact_zero,
            'conflicting_evidence': local_conflict,
            'unmatched_source_function_spans': unmatched_func - exact - local_conflict,
            'unmatched_source_assembly_spans': unmatched_asm - exact - local_conflict - unmatched_func,
            'unmatched_source_zero_initialized_data': unmatched_zero - exact - local_conflict - unmatched_func - unmatched_asm,
            'stale_source_checks': stale - exact - local_conflict - unmatched,
            'unchecked_source_spans': covered - exact - local_conflict - unmatched - stale,
            'gaps_without_source_check': universe - covered,
        }
        summaries[region] = {
            'start': start, 'end': end, 'denominator_bytes': end - start,
            'denominator_note': ('Stock scatter zero-fill extent, including unknown storage and alignment; not executable or initialized-flash bytes.'
                                 if region == 'zero_initialized_ram' else
                                 'Expanded initialized RAM including typed data, metadata and layout; not additional flash bytes.'
                                 if region == 'initialized_ram' else
                                 'Execution-region bytes including code, pools, tables, padding and other non-code; not a function or instruction denominator.'),
            'exact_unique_bytes': len(exact), 'source_covered_unique_bytes': len(covered),
            'exact_function_spans_code_and_pool_bytes': len(exact_func),
            'function_span_language': 'C (including source probes), excluding architectural assembly',
            'assembly_source_span_bytes': len(assembly),
            'exact_assembly_spans_code_and_pool_bytes': len(exact_asm),
            'zero_initialized_source_bytes': len(zero),
            'exact_zero_initialized_data_bytes': len(exact_zero),
            'explicitly_delimited_exact_code_bytes': len(code - local_conflict),
            'code_byte_count_note': 'Only gates explicitly separating instructions from pools contribute to this code-only count; all other exact functions remain code-plus-pool spans.',
            'generated_data_source_bytes': len(generated),
            'exact_generated_data_bytes': len(exact_generated - local_conflict),
            'exact_literal_pool_bytes': len(exact_pools - local_conflict),
            'exact_initialized_data_bytes': len(set().union(*[
                locations(row) & universe for row in records
                if row['kind'] == 'initialized_data' and row['status'] == 'exact']) - local_conflict),
            'known_data_and_pool_source_bytes': len(data),
            'exact_data_and_pool_bytes': len(exact_data),
            'function_data_overlap_bytes': len(exact_func & exact_data),
            'assembly_data_overlap_bytes': len(exact_asm & exact_data),
            'partitions': {key: {'bytes': len(value), 'intervals': intervals(value)}
                           for key, value in partitions.items()},
        }
        if sum(len(value) for value in partitions.values()) != end - start:
            raise ValueError('internal coverage partition overlap in ' + region)
    return summaries, duplicates, conflicts


def self_test():
    def row(name, start, size, status='exact', kind='function_span_code_and_pool'):
        return dict(gate=name, name=name, address=start, size=size, status=status, kind=kind)
    records = [row('probe', 0, 12), row('function', 0, 12),
               row('data', 8, 8, kind='generated_data'), row('open', 20, 4, 'unmatched')]
    regions, duplicates, conflicts = inventory(records)
    assert regions['itcm']['exact_unique_bytes'] == 16
    assert regions['itcm']['function_data_overlap_bytes'] == 4
    assert len(duplicates) == 1 and not conflicts
    assert regions['itcm']['partitions']['unmatched_source_function_spans']['bytes'] == 4
    regions, _, conflicts = inventory([row('a', 0, 12), row('b', 0, 12, 'unmatched')])
    assert regions['itcm']['exact_unique_bytes'] == 0 and len(conflicts) == 1
    reference = dict(row('c_reference', 0, 14, 'unmatched'), evidence_role='semantic_reference')
    regions, _, conflicts = inventory([reference, row('handler', 0, 14, kind=ASM_KIND)])
    assert not conflicts and regions['itcm']['exact_assembly_spans_code_and_pool_bytes'] == 14
    assert regions['itcm']['exact_function_spans_code_and_pool_bytes'] == 0
    regions, _, _ = inventory([row('old', 0, 12, 'stale')])
    assert regions['itcm']['exact_unique_bytes'] == 0
    regions, _, _ = inventory([row('state', 0x24000000, 16, kind='initialized_data')])
    assert regions['initialized_ram']['exact_unique_bytes'] == 16
    assert regions['initialized_ram']['exact_initialized_data_bytes'] == 16
    assert regions['initialized_ram']['exact_function_spans_code_and_pool_bytes'] == 0
    zi_start, zi_end = REGIONS['zero_initialized_ram']
    records = [row('c', 0, 12), row('asm', 0x080003a4, 20, kind=ASM_KIND),
               row('bss', zi_start, 16, kind=ZERO_KIND)]
    regions, _, conflicts = inventory(records)
    assert not conflicts
    assert regions['flash']['exact_function_spans_code_and_pool_bytes'] == 0
    assert regions['flash']['exact_assembly_spans_code_and_pool_bytes'] == 20
    assert regions['zero_initialized_ram']['exact_zero_initialized_data_bytes'] == 16
    assert regions['zero_initialized_ram']['exact_data_and_pool_bytes'] == 0
    assert regions['zero_initialized_ram']['exact_function_spans_code_and_pool_bytes'] == 0
    assert sum(r['exact_unique_bytes'] for name, r in regions.items()
               if name != 'zero_initialized_ram') == 32
    regions, _, conflicts = inventory([row('c', 0, 12), row('asm', 0, 12, kind=ASM_KIND)])
    assert len(conflicts) == 1 and regions['itcm']['exact_unique_bytes'] == 0
    regions, _, _ = inventory([row('asm', 0, 12, 'stale', ASM_KIND),
                               row('bss', zi_start, 16, 'stale', ZERO_KIND)])
    assert not regions['itcm']['exact_assembly_spans_code_and_pool_bytes']
    assert not regions['zero_initialized_ram']['exact_zero_initialized_data_bytes']
    zero_region = dict(address=zi_start, size=zi_end - zi_start)
    zero_row = dict(name='bss', address=zi_start, size=16, kind=ZERO_KIND,
                    exact=True, expected_sha256=hashlib.sha256(bytes(16)).hexdigest())
    assert normal_row(zero_row, 'bss', {'stale': False}, b'',
                      zero_region=zero_region)['status'] == 'exact'
    for fixture, proof in ((zero_row, None),
                           ({**zero_row, 'expected_sha256': 'bad'}, zero_region),
                           ({**zero_row, 'kind': 'initialized_data'}, zero_region),
                           ({**zero_row, 'address': zi_start - 16}, zero_region),
                           ({**zero_row, 'actual_sha256': 'bad'}, zero_region)):
        try:
            normal_row(fixture, 'bss', {'stale': False}, b'', zero_region=proof)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid zero-data evidence accepted')
    legacy_asm = normal_row(dict(name='asm', address=0, size=12, exact=True),
                            'runtime', {'stale': False})
    assert legacy_asm['kind'] == ASM_KIND
    assert normal_row(dict(name='c', address=0, size=12, kind='function'),
                      'base', {'stale': False})['kind'] == 'function_span_code_and_pool'
    assert intervals({0, 1, 3}) == [dict(start=0, end=2, size=2), dict(start=3, end=4, size=1)]
    source = Path(__file__).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    for commands in ([['clang', '-c', str(source)]],
                     [dict(argv=['clang', '-c', str(source)], source_sha256=digest)]):
        result = freshness('fixture', source,
                           dict(commands=commands, source_sha256={str(source): digest}))
        assert not result['stale']
        assert result['sources'] == [dict(path=str(source), status='hash_matches')]
    print('PASS: interval union, probe deduplication, data overlap, conflicts, stale checks, '
          'address zero, separate C/assembly/ZI accounting, zero-region/hash guards '
          'and both command-metadata schemas.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-progress.json')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    gates = DEFAULTS.copy()
    for override in args.gate:
        if '=' not in override:
            parser.error('--gate requires NAME=PATH')
        name, path = override.split('=', 1)
        gates[name] = Path(path).resolve()
    stock = STOCK.read_bytes()
    stock_sha = hashlib.sha256(stock).hexdigest()
    if hashlib.md5(stock).hexdigest() != MD5:
        parser.error('unsupported stock image: address profile does not apply')
    ram, _ = decompress(stock[0x3778:], 11912)
    zero_region = stock_zero_region(stock)
    records, reports, warnings = [], [], []
    for name, path in gates.items():
        if not path.is_file():
            reports.append(dict(name=name, path=str(path), status='missing'))
            warnings.append('Missing verification report: ' + name)
            continue
        try:
            payload = json.loads(path.read_text())
            state = freshness(name, path, payload)
            rows = payload if isinstance(payload, list) else payload.get('results', payload.get('functions', []))
            if isinstance(payload, dict):
                recorded_md5 = payload.get('stock_md5')
                recorded_sha = payload.get('stock_sha256', payload.get('image_sha256'))
                if recorded_md5 and recorded_md5 != MD5 or recorded_sha and recorded_sha != stock_sha:
                    raise ValueError('stock hash mismatch')
                if not (recorded_md5 or recorded_sha):
                    warnings.append(name + ': report does not record a stock hash')
                if name == 'bss' or any(row.get('kind') == ZERO_KIND for row in rows):
                    if payload.get('zero_region') != zero_region:
                        raise ValueError('BSS report lacks matching explicit stock zero-fill region')
            else:
                warnings.append(name + ': legacy report has no compiler/stock/source metadata')
            if not rows:
                raise ValueError('no function/data result rows; extraction alone is not a verification gate')
            gate_records = [normal_row(row, name, state, stock, ram, zero_region) for row in rows]
            records.extend(gate_records)
            configuration = ({key: payload[key] for key in
                              ('compiler', 'compiler_version', 'flags', 'command', 'commands',
                               'compiler_command', 'invocation', 'errors') if key in payload}
                             if isinstance(payload, dict) else {})
            reports.append(dict(name=name, path=str(path), status='stale' if state['stale'] else 'loaded',
                                freshness=state, rows=len(gate_records), configuration=configuration))
            if state['stale']:
                warnings.append(name + ': stale/missing source inputs; reported exact bytes excluded')
            if any(s['status'] == 'mtime_only_not_content_pinned' for s in state['sources']):
                warnings.append(name + ': some source freshness relies only on modification time')
            if isinstance(payload, dict) and payload.get('all_requested_gates_passed') is False:
                warnings.append(name + ': some requested gates failed; only exact result rows contribute')
        except (ValueError, TypeError, KeyError) as error:
            reports.append(dict(name=name, path=str(path), status='invalid', error=str(error)))
            warnings.append(name + ': invalid gate: ' + str(error))
    manifest_path = RECOVERED / 'generated/data-manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('image_sha256') != stock_sha:
            warnings.append('Generated source manifest stock hash mismatch; ignored')
        else:
            for row in manifest['sections']:
                entry = normal_row({**row, 'kind': 'generated_data'}, 'generated_manifest', {'stale': False})
                # A manifest proves source representation, never a byte-match gate.
                entry['status'] = 'unchecked'
                records.append(entry)
    else:
        warnings.append('Generated source manifest is missing')
    regions, duplicates, conflicts = inventory(records)
    if conflicts:
        warnings.append('Conflicting function evidence excluded from exact coverage: %d overlaps' % len(conflicts))
    report = dict(schema_version=2, scope='source-check inventory, not whole-firmware matching',
                  stock=dict(path=str(STOCK), size=len(stock), md5=MD5, sha256=stock_sha),
                  stock_zero_region=zero_region,
                  count_policy='Union runtime addresses. C and architectural assembly spans are separate and include pools, not inferred instruction bytes. Explicit semantic references remain recorded but do not contribute active coverage or conflicts. Data has exclusive accounting priority. Expanded initialized RAM is not a flash-byte count; zero-initialized RAM has its own region and is excluded from the legacy exact_unique_bytes summary.',
                  gate_reports=reports, records=records, regions=regions,
                  semantic_references=[row for row in records if row.get('evidence_role') == 'semantic_reference'],
                  duplicate_function_evidence=duplicates, conflicts=conflicts, warnings=warnings)
    report['summary'] = {
        'exact_unique_bytes': sum(r['exact_unique_bytes'] for name, r in regions.items()
                                  if name != 'zero_initialized_ram'),
        'exact_function_spans_code_and_pool_bytes': sum(
            r['exact_function_spans_code_and_pool_bytes'] for r in regions.values()),
        'exact_generated_data_bytes': sum(r['exact_generated_data_bytes'] for r in regions.values()),
        'exact_data_and_pool_bytes': sum(r['exact_data_and_pool_bytes'] for r in regions.values()),
        'exact_initialized_data_bytes': sum(r['exact_initialized_data_bytes'] for r in regions.values()),
        'exact_assembly_spans_code_and_pool_bytes': sum(
            r['exact_assembly_spans_code_and_pool_bytes'] for r in regions.values()),
        'exact_zero_initialized_data_bytes': regions['zero_initialized_ram']['exact_zero_initialized_data_bytes'],
        'zero_initialized_source_bytes': regions['zero_initialized_ram']['zero_initialized_source_bytes'],
        'function_data_overlap_bytes': sum(r['function_data_overlap_bytes'] for r in regions.values()),
        'unmatched_source_function_span_bytes': sum(
            r['partitions']['unmatched_source_function_spans']['bytes'] for r in regions.values()),
        'unmatched_source_assembly_span_bytes': sum(
            r['partitions']['unmatched_source_assembly_spans']['bytes'] for r in regions.values()),
        'missing_or_invalid_gates': [r['name'] for r in reports if r['status'] in ('missing', 'invalid')],
        'stale_gates': [r['name'] for r in reports if r['status'] == 'stale'],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    for name, region in regions.items():
        p = region['partitions']
        if name == 'zero_initialized_ram':
            print('ZERO-INITIALIZED RAM: typed exact %d/%d bytes; unclassified gaps %d; '
                  'excluded from C, initialized data and total exact union.' %
                  (region['exact_zero_initialized_data_bytes'], region['denominator_bytes'],
                   p['gaps_without_source_check']['bytes']))
            continue
        print('%s: exact unique %d/%d region bytes; function spans %d (code+pool), '
              'assembly spans %d (code+pool), known data/pools %d (generated %d); '
              'unmatched C source %d; gaps %d' %
              (name.upper(), region['exact_unique_bytes'], region['denominator_bytes'],
               region['exact_function_spans_code_and_pool_bytes'],
               region['exact_assembly_spans_code_and_pool_bytes'], region['exact_data_and_pool_bytes'],
               region['exact_generated_data_bytes'],
               p['unmatched_source_function_spans']['bytes'], p['gaps_without_source_check']['bytes']))
    print('%d duplicate function records deduplicated; %d conflicting overlaps.' % (len(duplicates), len(conflicts)))
    print('Total exact runtime-address union (excluding ZI): %d bytes; %d bytes overlap C function and data/pool evidence '
          '(already counted once).' % (report['summary']['exact_unique_bytes'],
                                       report['summary']['function_data_overlap_bytes']))
    for warning in warnings:
        print('WARNING: ' + warning)
    print('JSON: ' + str(args.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
