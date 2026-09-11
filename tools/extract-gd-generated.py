#!/usr/bin/env python3
"""Extract mainBoardGD's shipped generated command layer as validated JSON.

Usage (from any directory):
  python3 tools/extract-gd-generated.py --out work/mainBoardGD-generated.json

Requires Python 3 and capstone (no compiler). Uses scatterload.py beside this
file. The address profile is for the 45,552-byte mainBoardGD stock image;
this is deliberately not a heuristic extractor for other firmware versions.
Optional --itcm/--data files must equal the regions unpacked from --image.

Parser fields and parameter bytes are read from stock, then checked against
the embedded dictionary and retained .ctr. Lookup mappings are recovered by
interpreting the small, bounded Thumb lookup routines (strcmp is modeled),
including every matching return and the unknown-string return. Unsupported
instructions, bad pointers, truncated regions and inconsistent metadata fail.
Addresses in JSON are integers in the MCU runtime address space. Original
struct bytes and the compressed identify bytes are included as hex; the
dictionary is decoded, never recompressed. Nothing here claims recovered C
syntax or a byte-identical firmware rebuild.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

import scatterload


ROOT = Path(__file__).resolve().parents[1]
FLASH = 0x08000000
TABLE = 0x08003744
ITCM_SIZE = 28120
DATA_BASE = 0x24000000
DATA_SIZE = 11912
COMMAND_INDEX = 0x6560
COMMAND_INDEX_SIZE = 0x6880
IDENTIFY = 0x5d98
IDENTIFY_SIZE = 0x655c
ENCODER_START, ENCODER_END = 0x21a0, 0x2390
STATIC_START, STATIC_END = 0x2420, 0x2738
STRCMP_VENEER = 0x5b8a
STRCMP = 0x08000458
PT = ['uint32', 'int32', 'uint16', 'int16', 'byte',
      'string', 'progmem_buffer', 'buffer']
FORMAT_TYPES = dict(zip(['%u', '%i', '%hu', '%hi', '%c', '%s', '%.*s', '%*s'],
                        range(8)))
MAX_LENGTH = [5, 5, 3, 3, 2, 64, 64, 64]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(blob, address, size, base=0):
    offset = address - base
    require(size >= 0 and 0 <= offset <= len(blob) - size,
            'out-of-range read at %#x, size %d' % (address, size))
    return blob[offset:offset + size]


def unpack(fmt, blob, address, base=0):
    return struct.unpack(fmt, read(blob, address, struct.calcsize(fmt), base))


def cstring(blob, address):
    read(blob, address, 1)
    end = blob.find(b'\0', address)
    require(end >= address, 'unterminated string at %#x' % address)
    value = blob[address:end].decode('ascii')
    require(value and all(32 <= ord(c) <= 126 for c in value),
            'non-text string at %#x' % address)
    return value


def regions(image):
    require(len(image) == 45552, 'image size does not match the mainBoardGD profile')
    result, metadata = {}, []
    expected = [(DATA_BASE, DATA_SIZE, 'decompress'), (0, ITCM_SIZE, 'copy'),
                (0x24002e88, 33976, 'zeroinit')]
    for index, (dst_expected, size_expected, kind_expected) in enumerate(expected):
        src, dst, size, fn = unpack('<4I', image, TABLE + 16 * index, FLASH)
        helper = read(image, fn, 8, FLASH)
        kind = scatterload.HELPERS.get(helper)
        require((dst, size, kind) == (dst_expected, size_expected, kind_expected),
                'unexpected scatterload entry %d' % index)
        used = 0
        if kind == 'decompress':
            source = read(image, src, 0x08004418 - src, FLASH)
            blob, used = scatterload.decompress(source, size)
            require(len(blob) == size and 0 < used <= len(source),
                    'invalid decompressed region length')
            result[dst] = blob
        elif kind == 'copy':
            result[dst] = read(image, src, size, FLASH)
            used = size
        metadata.append(dict(source_address=src, destination_address=dst,
                             size=size, helper_address=fn, kind=kind,
                             source_bytes_consumed=used))
    return result[0], result[DATA_BASE], metadata


class Lookup:
    """Restricted evaluator: only the instructions observed in these lookups."""
    def __init__(self, itcm, start, end):
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
        self.itcm, self.start = itcm, start
        decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        self.instructions = {i.address: i for i in
                             decoder.disasm(read(itcm, start, end - start), start)}
        require(sum(i.size for i in self.instructions.values()) == end - start,
                'incomplete lookup disassembly')

    def run(self, query):
        registers, comparisons = {'r0': query}, []
        pc, equal = self.start, None

        def value(operand):
            if operand.startswith('#'):
                return int(operand[1:], 0)
            require(operand in registers, 'read of unset register ' + operand)
            return registers[operand]

        for _ in range(1000):
            require(pc in self.instructions, 'lookup branched outside its code')
            insn = self.instructions[pc]
            pc += insn.size
            name = insn.mnemonic.removesuffix('.w')
            operands = insn.op_str.split(', ')
            if name == 'push':
                require(insn.op_str == '{r4, lr}', 'unexpected lookup prologue')
            elif name == 'pop':
                require(insn.op_str == '{r4, pc}', 'unexpected lookup epilogue')
                return registers['r0'], comparisons
            elif name == 'adr':
                registers[operands[0]] = ((insn.address + 4) & ~3) + value(operands[1])
            elif name in ('mov', 'movs', 'movw', 'movt', 'moveq', 'movne'):
                if name in ('moveq', 'movne'):
                    require(equal is not None, 'conditional move without comparison')
                    if equal != (name == 'moveq'):
                        continue
                destination, source = operands
                v = value(source)
                if name == 'movt':
                    v = (value(destination) & 0xffff) | (v << 16)
                registers[destination] = v
                if name == 'movs':
                    equal = v == 0
            elif name == 'bl':
                require(value(operands[0]) == STRCMP_VENEER,
                        'unexpected lookup call at %#x' % insn.address)
                require(registers.get('r0') == query, 'strcmp input was not preserved')
                address = registers['r1']
                text = cstring(self.itcm, address)
                comparisons.append(dict(call_address=insn.address,
                                        string_address=address, text=text))
                registers['r0'] = 0 if query == text else 1
            elif name == 'cmp':
                equal = value(operands[0]) == value(operands[1])
            elif name == 'beq':
                require(equal is not None, 'branch without comparison')
                if equal:
                    pc = value(operands[0])
            elif name == 'it':
                require(insn.op_str in ('eq', 'ne'), 'unsupported IT block')
            elif name == 'uxtb':
                registers[operands[0]] = value(operands[1]) & 0xff
            else:
                raise ValueError('unsupported lookup instruction at %#x: %s %s'
                                 % (insn.address, insn.mnemonic, insn.op_str))
        raise ValueError('lookup did not terminate')

    def extract(self, fallback):
        actual, comparisons = self.run(None)
        require(actual == fallback, 'unexpected lookup fall-through')
        require(len({c['text'] for c in comparisons}) == len(comparisons),
                'duplicate lookup comparison')
        for comparison in comparisons:
            result, _ = self.run(comparison['text'])
            comparison['result'] = result
        return comparisons


def parameters(itcm, pointer, count, message):
    require(pointer != 0 or count == 0, 'null parameter pointer with nonzero count')
    require(pointer == 0 or count != 0, 'parameter pointer on a parameterless message')
    codes = list(read(itcm, pointer, count))
    require(all(code < len(PT) for code in codes), 'invalid parameter type')
    expected, names = [], []
    for field in message.split()[1:]:
        name, fmt = field.split('=', 1)
        require(fmt in FORMAT_TYPES, 'unsupported parameter format ' + fmt)
        names.append(name)
        expected.append(FORMAT_TYPES[fmt])
    require(codes == expected, 'parameter types disagree with dictionary: ' + message)
    return [dict(name=name, type_code=code, type=PT[code])
            for name, code in zip(names, codes)]


def extract(image):
    itcm, data, metadata = regions(image)
    # Check that the modeled call really goes through the known strcmp veneer.
    require(read(itcm, STRCMP_VENEER, 10).hex() == '40f2594cc0f6000c6047',
            'strcmp veneer changed')
    require(read(image, STRCMP, 28, FLASH).hex() ==
            '10b5002200e0521c835c8c5ca34201d1002bf8d1d8b2e1b2401a10bd',
            'strcmp implementation changed')

    blob_size, = unpack('<I', itcm, IDENTIFY_SIZE)
    blob = read(itcm, IDENTIFY, blob_size)
    decoder = zlib.decompressobj()
    dictionary_bytes = decoder.decompress(blob, 1000000)
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'identify length does not describe exactly one complete zlib stream')
    dictionary = json.loads(dictionary_bytes)
    require(dictionary.get('app') == 'Klipper', 'identify is not a Klipper dictionary')
    require(IDENTIFY + blob_size <= IDENTIFY_SIZE, 'identify overlaps its size field')

    requests = []
    for match in re.finditer(rb'(?<![ -~])_?DECL_[\x09\x20-\x7e]*', data):
        require(read(data, match.end(), 1) == b'\0', 'unterminated .ctr request')
        requests.append(dict(address=DATA_BASE + match.start(),
                             text=match.group().decode('ascii')))
    require(len(requests) == 144, 'expected 144 retained .ctr requests')
    handlers, declarations = {}, {}
    for request in requests:
        if request['text'].startswith('DECL_COMMAND_FLAGS '):
            _, handler, flags, message = request['text'].split(None, 3)
            require(message not in handlers, 'duplicate command declaration')
            require(flags in ('0', '0x01', 'HF_IN_SHUTDOWN'), 'unknown command flag ' + flags)
            handlers[message] = handler
            declarations[message] = (request['address'], int(flags != '0'))

    count, = unpack('<H', itcm, COMMAND_INDEX_SIZE)
    require(count == 50 and COMMAND_INDEX + count * 16 == COMMAND_INDEX_SIZE,
            'invalid command_index_size or table extent')
    by_id = {v: k for k, v in dictionary['commands'].items()}
    require(len(by_id) == 49 and set(by_id) == set(range(1, count)),
            'unexpected dictionary command ids')
    require(set(handlers) == set(dictionary['commands']),
            '.ctr command formats differ from dictionary')
    commands = []
    for index in range(count):
        address = COMMAND_INDEX + index * 16
        raw = read(itcm, address, 16)
        encoded, nargs, flags, nparams, padding, pointer, function = struct.unpack(
            '<HBBB3sII', raw)
        if index == 0:
            require(raw == bytes(16), 'nonzero reserved command_index[0]')
            commands.append(dict(index=0, address=address, raw_hex=raw.hex(), reserved=True))
            continue
        message = by_id[index]
        require(encoded == index and padding == bytes(3), 'invalid parser id/padding')
        require(function & 1 and 0 <= (function & ~1) < ENCODER_START,
                'invalid command handler pointer')
        params = parameters(itcm, pointer, nparams, message)
        require(nargs == nparams + sum(p['type_code'] in (6, 7) for p in params),
                'incorrect command argument count: ' + message)
        ctr_address, expected_flags = declarations[message]
        require(flags == expected_flags, 'command flags differ from .ctr: ' + message)
        commands.append(dict(index=index, address=address, raw_hex=raw.hex(),
                             encoded_msgid=encoded, msgid=index, format=message,
                             num_args=nargs, flags=flags, num_params=nparams,
                             param_types_address=pointer, parameters=params,
                             handler_pointer=function, handler_address=function & ~1,
                             handler_name=handlers[message], declaration_address=ctr_address))

    lookup = Lookup(itcm, ENCODER_START, ENCODER_END)
    encoders = []
    for comparison in lookup.extract(0):
        message, address = comparison['text'], comparison['result']
        raw = read(itcm, address, 8)
        encoded, max_size, nparams, pointer = struct.unpack('<HBBI', raw)
        require(message in dictionary['responses'], 'lookup message missing from dictionary')
        msgid = dictionary['responses'][message]
        require(0 <= msgid < 0x60 and encoded == msgid, 'encoder id mismatch')
        params = parameters(itcm, pointer, nparams, message)
        require(max_size == min(64, 6 + sum(MAX_LENGTH[p['type_code']] for p in params)),
                'encoder max_size mismatch: ' + message)
        encoders.append(dict(address=address, raw_hex=raw.hex(), encoded_msgid=encoded,
                             msgid=msgid, format=message, max_size=max_size,
                             num_params=nparams, param_types_address=pointer,
                             parameters=params, lookup_call_address=comparison['call_address'],
                             format_address=comparison['string_address']))
    require({e['format'] for e in encoders} == set(dictionary['responses']),
            'dictionary responses are not exactly covered by lookup')
    require(sorted(e['address'] for e in encoders) == list(range(0x5d08, IDENTIFY, 8)),
            'unexpected encoder table coverage')

    static_strings = Lookup(itcm, STATIC_START, STATIC_END).extract(255)
    require({s['text']: s['result'] for s in static_strings} ==
            dictionary['enumerations']['static_string_id'], 'static string lookup mismatch')
    declared_encoders = {r['text'].split(None, 1)[1] for r in requests
                         if r['text'].startswith('_DECL_ENCODER ')}
    generated_encoders = {e['format'] for e in encoders}
    missing = sorted(declared_encoders - generated_encoders)
    require(missing == ['param_value value=%u reserve=%u'],
            'unexpected .ctr/generated encoder discrepancy')
    require(not generated_encoders - declared_encoders, 'undeclared generated encoder')
    null_result, _ = lookup.run(missing[0])
    require(null_result == 0, 'missing encoder did not return NULL')

    return dict(schema_version=1, image=dict(size=len(image),
                    sha256=hashlib.sha256(image).hexdigest(), load_address=FLASH),
                regions=metadata, compile_time_requests=requests,
                command_index=dict(address=COMMAND_INDEX, count=count,
                    size_address=COMMAND_INDEX_SIZE, entry_size=16, entries=commands),
                encoders=encoders, static_strings=static_strings,
                lookup_functions=dict(encoder_address=ENCODER_START, encoder_fallback=0,
                    static_string_address=STATIC_START, static_string_fallback=255),
                identify=dict(address=IDENTIFY, size_address=IDENTIFY_SIZE,
                    size=blob_size, uncompressed_size=len(dictionary_bytes),
                    compressed_hex=blob.hex(), sha256=hashlib.sha256(blob).hexdigest(),
                    dictionary=dictionary),
                discrepancies=dict(declared_but_missing_encoders=missing,
                    missing_encoder_lookup_result=null_result),
                validation=dict(command_formats_ids_flags_args_and_types=True,
                    response_formats_ids_sizes_and_types=True,
                    all_static_string_mappings=True,
                    exact_identify_zlib_stream=True)), itcm, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path,
                        default=ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin')
    parser.add_argument('--itcm', type=Path, help='optional unpacked ITCM cross-check')
    parser.add_argument('--data', type=Path, help='optional unpacked data cross-check')
    parser.add_argument('--out', type=Path, help='write JSON here instead of stdout')
    args = parser.parse_args()
    try:
        result, itcm, data = extract(args.image.read_bytes())
        for path, expected in ((args.itcm, itcm), (args.data, data)):
            if path is not None:
                require(path.read_bytes() == expected, 'unpacked region differs: ' + str(path))
        text = json.dumps(result, indent=2, sort_keys=True) + '\n'
        if args.out:
            args.out.write_text(text)
        else:
            sys.stdout.write(text)
    except (ValueError, IndexError, KeyError, OSError, ImportError, struct.error,
            zlib.error) as error:
        parser.exit(1, 'extraction failed: %s\n' % error)
    print('validated: 49 commands, %d encoders, %d static strings, 144 .ctr requests; '
          'param_value lookup returns NULL' % (len(result['encoders']),
                                               len(result['static_strings'])), file=sys.stderr)


if __name__ == '__main__':
    main()
