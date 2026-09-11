#!/usr/bin/env python3
"""Source-only candidate encoders for mainBoardGD's armlink scatter LZ77 format.

  python3 tools/gd_scatter_compress.py --self-test
  python3 tools/gd_scatter_compress.py

Default input is the partial link's source-built initialized-ram.bin. The
compress() function takes only those bytes and a generic parsing hypothesis;
stock bytes/tokens are read exclusively by the separate diagnostic comparison.
The retained lazy-lex128 algorithm reproduces the current stock stream exactly;
the earlier hypotheses remain available as explicit diagnostics. No stock-token
replay or address-specific exception participates in encoding. Exactness requires
the complete bytes and length to match, not merely a successful round-trip.
"""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

from scatterload import decompress

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES = ('greedy-nearest', 'lazy-nearest', 'lazy-oldest', 'lazy-bst',
              'lazy-lex257', 'lazy-fullsuffix', 'lazy-lex128')
CANONICAL_HYPOTHESIS = 'lazy-lex128'
MAX_MATCH, MAX_DISTANCE, MAX_LITERALS = 257, 65535, 254


def encode_token(literals, length=0, distance=0):
    if len(literals) > MAX_LITERALS or length and not 3 <= length <= MAX_MATCH:
        raise ValueError('token length out of range')
    if length and not 1 <= distance <= MAX_DISTANCE or not length and distance:
        raise ValueError('token distance out of range')
    literal_count = len(literals) + 1
    match_count = length - 2 if length else 0
    token = (literal_count if literal_count <= 3 else 0)
    token |= (match_count if 1 <= match_count <= 15 else 0) << 4
    if length:
        token |= ((distance >> 8) << 2) if distance < 768 else 12
    result = bytearray([token])
    if not token & 3:
        result.append(literal_count)
    if not token >> 4:
        result.append(match_count)
    result.extend(literals)
    if length:
        result.append(distance & 255)
        if distance >= 768:
            result.append(distance >> 8)
    return bytes(result)


class Matches:
    """Exhaustive three-byte index; no stock profile or token input."""
    def __init__(self, data):
        self.data = data
        self.index = defaultdict(list)
        for position in range(len(data) - 2):
            self.index[data[position:position + 3]].append(position)

    def best(self, position, oldest=False):
        data = self.data
        limit = min(MAX_MATCH, len(data) - position)
        if limit < 3:
            return 0, 0
        choices = self.index.get(data[position:position + 3], ())
        lo = bisect_left(choices, max(0, position - MAX_DISTANCE))
        hi = bisect_left(choices, position)
        indexes = range(lo, hi) if oldest else range(hi - 1, lo - 1, -1)
        best_length, best_distance = 0, 0
        for index in indexes:
            previous = choices[index]
            if best_length and data[previous + best_length] != data[position + best_length]:
                continue
            length = 3
            while length < limit and data[previous + length] == data[position + length]:
                length += 1
            if length > best_length:
                best_length, best_distance = length, position - previous
                if length == limit:
                    break
        return best_length, best_distance


class LexicographicMatches:
    """Adjacent suffix keys; canonical keys retain their newest representative.

    Ordering uses at most 128 bytes, but the selected match extends up to 257.
    Keys, positions and window expiry come exclusively from input bytes. The
    257/full-suffix variants preserve duplicate entries for historical tests.
    """
    def __init__(self, data, key_limit=128, unique=True, window=MAX_DISTANCE):
        keys, representatives, self.matches = [], {}, []
        for position in range(len(data)):
            expired = position - window - 1
            if expired >= 0:
                expired_key = data[expired:expired + key_limit] if key_limit else data[expired:]
                if unique:
                    if representatives.get(expired_key) == expired:
                        keys.pop(bisect_left(keys, expired_key))
                        del representatives[expired_key]
                else:
                    keys.pop(bisect_left(keys, (expired_key, expired)))
            key = data[position:position + key_limit] if key_limit else data[position:]
            lookup = key if unique else (key, position)
            index = bisect_left(keys, lookup)
            best_length, best_distance = 0, 0
            for neighbor in (index - 1, index):
                if not 0 <= neighbor < len(keys):
                    continue
                previous = representatives[keys[neighbor]] if unique else keys[neighbor][1]
                length, limit = 0, min(MAX_MATCH, len(data) - position)
                while length < limit and data[previous + length] == data[position + length]:
                    length += 1
                # Visit predecessor first; successor wins equal-length ties.
                if length >= 3 and length >= best_length:
                    best_length, best_distance = length, position - previous
            self.matches.append((best_length, best_distance))
            if unique:
                if key not in representatives:
                    keys.insert(index, key)
                representatives[key] = position
            else:
                keys.insert(index, lookup)

    def best(self, position, oldest=False):
        return self.matches[position] if 0 <= position < len(self.matches) else (0, 0)


class BinaryTreeMatches:
    """Rejected diagnostic: input-order BST, first longest along search path.

    Equal 257-byte keys replace the prior representative. Expired references
    cannot produce matches, although their nodes retain traversal history.
    """
    def __init__(self, data):
        root = -1
        left, right = [-1] * len(data), [-1] * len(data)
        keys = [data[p:p + MAX_MATCH] for p in range(len(data))]
        self.matches = []
        for position, key in enumerate(keys):
            node, parent, side, best = root, -1, None, (0, 0)
            while node != -1:
                previous_key, length = keys[node], 0
                limit = min(len(key), len(previous_key))
                while length < limit and key[length] == previous_key[length]:
                    length += 1
                if length >= 3 and length > best[0] and position - node <= MAX_DISTANCE:
                    best = length, position - node
                if key == previous_key:
                    left[position], right[position] = left[node], right[node]
                    break
                parent, side = node, left if key < previous_key else right
                node = side[node]
            if parent < 0:
                root = position
            else:
                side[parent] = position
            self.matches.append(best)

    def best(self, position, oldest=False):
        return self.matches[position] if 0 <= position < len(self.matches) else (0, 0)


def compress(data, hypothesis=CANONICAL_HYPOTHESIS):
    """Encode source bytes only, with an explicit generic dictionary/parser."""
    if hypothesis not in HYPOTHESES:
        raise ValueError('unknown hypothesis: ' + hypothesis)
    if hypothesis == 'lazy-bst':
        matches = BinaryTreeMatches(data)
    elif hypothesis == 'lazy-lex257':
        matches = LexicographicMatches(data, key_limit=257, unique=False)
    elif hypothesis == 'lazy-fullsuffix':
        matches = LexicographicMatches(data, key_limit=None, unique=False)
    elif hypothesis == CANONICAL_HYPOTHESIS:
        matches = LexicographicMatches(data)
    else:
        matches = Matches(data)
    oldest = hypothesis == 'lazy-oldest'
    lazy = hypothesis != 'greedy-nearest'
    result, literals = bytearray(), bytearray()
    position = 0
    while position < len(data):
        length, distance = matches.best(position, oldest)
        # Spending a literal only wins if the next match grows by at least two.
        # Stock has 58 such deferrals and no deferral for a mere +1 extension.
        if length and lazy and matches.best(position + 1, oldest)[0] > length + 1:
            length = 0
        if length:
            result.extend(encode_token(literals, length, distance))
            literals.clear()
            position += length
        else:
            literals.append(data[position])
            position += 1
            if len(literals) == MAX_LITERALS:
                result.extend(encode_token(literals))
                literals.clear()
    if literals:
        result.extend(encode_token(literals))
    return bytes(result)


def tokens(stream, output_size):
    """Bounded independent token inspection; never used by the encoder."""
    position, output, result = 0, 0, []

    def byte():
        nonlocal position
        if position >= len(stream):
            raise ValueError('truncated compressed token')
        value = stream[position]
        position += 1
        return value

    while output < output_size:
        offset, start = position, output
        token = byte()
        count = token & 3 or byte()
        encoded_length = token >> 4 or byte()
        if not count:
            raise ValueError('zero literal count field')
        literals = bytes(byte() for _ in range(count - 1))
        output += len(literals)
        distance, length = 0, 0
        if encoded_length:
            distance = byte()
            distance += byte() << 8 if token & 12 == 12 else (token & 12) << 6
            if not 1 <= distance <= output:
                raise ValueError('invalid back-reference distance')
            length = encoded_length + 2
        result.append(dict(compressed_offset=offset, compressed_size=position - offset,
                           output_start=start, match_start=output,
                           literal_count=len(literals), match_length=length,
                           distance=distance))
        output += length
        if output > output_size:
            raise ValueError('token overruns expanded region')
    return result, position


def compare(candidate, reference, output_size):
    actual, consumed = tokens(candidate, output_size)
    expected, used = tokens(reference, output_size)
    if consumed != len(candidate) or used != len(reference):
        raise ValueError('trailing compressed bytes')
    prefix = next((i for i, (a, b) in enumerate(zip(candidate, reference)) if a != b),
                  min(len(candidate), len(reference)))
    by_position = {t['match_start']: t for t in expected}
    common, same_lengths, same_distances, identical, differences = 0, 0, 0, 0, []
    for token in actual:
        other = by_position.get(token['match_start'])
        if other is None:
            continue
        common += 1
        same_lengths += token['match_length'] == other['match_length']
        same_distances += token['distance'] == other['distance']
        keys = ('output_start', 'match_start', 'literal_count', 'match_length', 'distance')
        if all(token[k] == other[k] for k in keys):
            identical += 1
        elif len(differences) < 12:
            differences.append(dict(match_start=token['match_start'],
                                    actual={k: token[k] for k in keys},
                                    expected={k: other[k] for k in keys}))
    return dict(exact=candidate == reference, size=len(candidate), expected_size=len(reference),
                prefix_bytes=prefix,
                positional_matching_bytes=sum(a == b for a, b in zip(candidate, reference)),
                token_count=len(actual), expected_token_count=len(expected),
                common_match_starts=common, same_match_lengths_at_common_starts=same_lengths,
                same_distances_at_common_starts=same_distances,
                identical_tokens_at_common_starts=identical, first_token_differences=differences,
                candidate_sha256=hashlib.sha256(candidate).hexdigest())


def analyze_reference(data, reference):
    observed, _ = tokens(reference, len(data))
    matches = Matches(data)
    counts, shorter, literal_matches, kept_matches = Counter(), [], [], []
    for token in observed:
        position, length, distance = token['match_start'], token['match_length'], token['distance']
        if length:
            longest, nearest = matches.best(position)
            _, oldest = matches.best(position, True)
            counts['match_tokens'] += 1
            if length == longest:
                counts['longest_available_match'] += 1
                counts['nearest_longest'] += distance == nearest
                counts['oldest_longest'] += distance == oldest
            else:
                counts['shorter_than_longest'] += 1
                shorter.append(dict(position=position, stock_length=length,
                                    stock_distance=distance, longest=longest, nearest=nearest))
            next_length, _ = matches.best(position + 1)
            if next_length > length:
                kept_matches.append(dict(position=position, length=length,
                                         next_length=next_length, distance=distance))
        for position in range(token['output_start'], token['match_start']):
            available, distance = matches.best(position)
            if available:
                counts['literal_positions_with_available_match'] += 1
                next_length, _ = matches.best(position + 1)
                counts['literal_positions_explained_by_one_byte_lazy'] += next_length > available
                counts['literal_positions_with_net_lazy_gain'] += next_length > available + 1
                if len(literal_matches) < 12:
                    literal_matches.append(dict(position=position, available=available,
                                                distance=distance, next_length=next_length))
    return dict(counts=dict(counts), shorter_matches=shorter,
                kept_matches_despite_longer_next=kept_matches,
                maximum_distance=max(t['distance'] for t in observed),
                maximum_match_length=max(t['match_length'] for t in observed),
                maximum_literal_count=max(t['literal_count'] for t in observed),
                literal_match_examples=literal_matches)


def self_test():
    rng = random.Random(0)
    samples = [b'', b'a', b'ab', b'abc', bytes(range(256)), b'\0' * 1200,
               b'ab' * 700, b'abcde' * 300,
               bytes(rng.randrange(256) for _ in range(1800)),
               b'COMMAND oid=%c value=%u\0' * 80]
    for hypothesis in HYPOTHESES:
        for sample in samples:
            encoded = compress(sample, hypothesis)
            decoded, used = decompress(encoded, len(sample))
            assert decoded == sample and used == len(encoded)
            _, used = tokens(encoded, len(sample))
            assert used == len(encoded)
    for distance in (1, 255, 256, 511, 512, 767, 768, 65535):
        prefix = bytes(rng.randrange(256) for _ in range(distance))
        for length in (3, 17, 18, 257):
            stream = b''.join(encode_token(prefix[i:i + MAX_LITERALS])
                              for i in range(0, len(prefix), MAX_LITERALS))
            stream += encode_token(b'', length, distance)
            expected = bytearray(prefix)
            for _ in range(length):
                expected.append(expected[-distance])
            decoded, used = decompress(stream, len(expected))
            assert decoded == expected and used == len(stream)
    for literals in (0, 1, 2, 3, 254):
        prefix = bytes(range(literals))
        if prefix:
            stream = encode_token(prefix)
            assert decompress(stream, len(prefix)) == (prefix, len(stream))
    for args in ((b'x' * 255, 0, 0), (b'', 2, 1), (b'', 258, 1),
                 (b'', 3, 0), (b'', 3, 65536)):
        try:
            encode_token(*args)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid token accepted')
    # Independent synthetic long-key behavior: ordering truncates at 128, but
    # repeated matches may extend well beyond that. No firmware bytes are used.
    samples = [b'\0' * 133 + b'A' + b'\0' * 134 + b'B',
               bytes(range(128)) * 8, b'abc' * 22000,
               b'x' * 130 + b'A' + b'x' * 130 + b'B' + b'x' * 260]
    for sample in samples:
        stream = compress(sample)
        assert decompress(stream, len(sample)) == (sample, len(stream))
        inspected, used = tokens(stream, len(sample))
        assert used == len(stream) and all(t['distance'] <= MAX_DISTANCE for t in inspected)
    repeated_key = bytes(range(128))
    collision = repeated_key + b'A' + repeated_key + b'B' + repeated_key + b'C'
    assert LexicographicMatches(collision).best(258) == (128, 129)
    assert LexicographicMatches(b'\0' * 600).best(1) == (257, 1)
    # The older lexicographically greater suffix wins a length-three tie,
    # independently distinguishing this rule from nearest-distance matching.
    assert LexicographicMatches(b'abcN111abcL000abcM222').best(14) == (3, 14)
    # Exercise actual key removal at a smaller window, rather than requiring
    # large incompressible fixtures just to reach 65,535-byte expiry.
    sample = bytes(range(64)) * 3
    limited = LexicographicMatches(sample, window=32)
    assert all(length == 0 for length, distance in limited.matches)
    malformed = [(b'', 1), (b'\x00\x00\x00', 1), (b'\x12x\x00', 4),
                 (b'\x11\x01', 3), (encode_token(b'ab'), 1),
                 (encode_token(b'a', 3, 1), 3)]
    for stream, size in malformed:
        try:
            tokens(stream, size)
        except ValueError:
            pass
        else:
            raise AssertionError('malformed stream accepted')
    stream = compress(b'abc')
    try:
        compare(stream + b'\0', stream, 3)
    except ValueError:
        pass
    else:
        raise AssertionError('trailing compressed bytes accepted')
    print('self-test: all dictionary/parser hypotheses round-trip; token boundaries, '
          '128-byte key collisions, window expiry and malformed inputs pass')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path,
                        default=ROOT / 'work/mainBoardGD-partial/initialized-ram.bin')
    parser.add_argument('--out', type=Path, default=ROOT / 'work/mainBoardGD-compression')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--hypothesis', choices=HYPOTHESES)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    data = args.input.read_bytes()
    image = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    expanded, used = decompress(image[0x3778:], 11912)
    reference = image[0x3778:0x3778 + used]
    if data != expanded:
        raise ValueError('source RAM must first match the complete stock expanded RAM')
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for hypothesis in (args.hypothesis,) if args.hypothesis else HYPOTHESES:
        candidate = compress(data, hypothesis)
        decoded, consumed = decompress(candidate, len(data))
        if decoded != data or consumed != len(candidate):
            raise ValueError('candidate failed round-trip: ' + hypothesis)
        (args.out / (hypothesis + '.bin')).write_bytes(candidate)
        result = dict(hypothesis=hypothesis, round_trip=True,
                      **compare(candidate, reference, len(data)))
        results.append(result)
        print('%s: %d/%d compressed bytes; prefix %d; %d/%d identical stock tokens; %s'
              % (hypothesis, result['size'], used, result['prefix_bytes'],
                 result['identical_tokens_at_common_starts'], result['expected_token_count'],
                 'EXACT' if result['exact'] else 'DIFF'))
    report = dict(scope='source-only scatter compression hypotheses; exact:false is not an image match',
                  input=str(args.input.resolve()), input_size=len(data),
                  input_sha256=hashlib.sha256(data).hexdigest(),
                  image_sha256=hashlib.sha256(image).hexdigest(),
                  reference_sha256=hashlib.sha256(reference).hexdigest(),
                  source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):
                                 hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                 'tools/scatterload.py':
                                 hashlib.sha256((ROOT / 'tools/scatterload.py').read_bytes()).hexdigest()},
                  lazy_rule='defer one byte only if next_match_length > current_match_length + 1',
                  canonical_hypothesis=CANONICAL_HYPOTHESIS,
                  canonical_dictionary=dict(key_bytes=128, duplicate_key='newest input position',
                                            candidates='lexicographic predecessor and successor',
                                            equal_length_tie='successor', maximum_match=MAX_MATCH,
                                            maximum_distance=MAX_DISTANCE),
                  stock_analysis=analyze_reference(data, reference), results=results,
                  any_exact=any(r['exact'] for r in results))
    report_path = args.report or args.out / 'results.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return int(not report['any_exact'])


if __name__ == '__main__':
    raise SystemExit(main())
