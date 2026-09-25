"""核心口径的单元测试：随机生成的时钟对照朴素参考实现。"""

import functools
import random
import tempfile
import unittest
from pathlib import Path

from causalline import core


def write_events(path, events):
    lines = []
    for eid, node, wall, clock in events:
        body = ",".join("%s:%d" % (name, clock[name]) for name in sorted(clock))
        lines.append("%s %s %d %s" % (eid, node, wall, body))
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")


def ref_relation(clock_a, clock_b):
    less = greater = False
    for name in set(clock_a) | set(clock_b):
        val_a = clock_a.get(name, 0)
        val_b = clock_b.get(name, 0)
        if val_a < val_b:
            less = True
        elif val_a > val_b:
            greater = True
    if less and greater:
        return core.INCOMP
    if less:
        return core.LT
    if greater:
        return core.GT
    return core.INCOMP


def ref_order(events):
    def compare(first, second):
        clock_a, clock_b = first[3], second[3]
        for name in sorted(set(clock_a) | set(clock_b)):
            val_a = clock_a.get(name, 0)
            val_b = clock_b.get(name, 0)
            if val_a != val_b:
                return -1 if val_a < val_b else 1
        return (first[0] > second[0]) - (first[0] < second[0])

    return sorted(events, key=functools.cmp_to_key(compare))


def random_events(rng, count):
    nodes = ["n%02d" % i for i in range(rng.randint(1, 8))]
    events = []
    for i in range(count):
        node = rng.choice(nodes)
        clock = {node: rng.randint(1, 5)}
        for other in nodes:
            if other != node and rng.random() < 0.35:
                clock[other] = rng.randint(1, 5)
        events.append(("e%03d" % i, node, rng.randint(0, 10 ** 6), clock))
    return events


class EncTest(unittest.TestCase):
    def test_enc_preserves_order(self):
        rng = random.Random(7)
        values = [0, 1, 2, 255, 256, 65535, 65536, 2 ** 32, 2 ** 64 + 1]
        values += [rng.randint(0, 2 ** 40) for _ in range(200)]
        encoded = [core._enc(v) for v in values]
        self.assertEqual(sorted(values), [v for _, v in
                                          sorted(zip(encoded, values))])

    def test_enc_first_byte_nonzero(self):
        for value in (0, 1, 127, 300, 2 ** 20):
            self.assertGreater(core._enc(value)[0], 0)


class RelationTest(unittest.TestCase):
    def check_batch(self, events):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.txt"
            write_events(path, events)
            log = core.parse(str(path), keep_meta=True)
        self.assertEqual(len(log), len(events))
        by_id = {event[0]: i for i, event in enumerate(events)}
        for first in events:
            for second in events:
                got = core.relate(log, by_id[first[0]], by_id[second[0]])
                want = ref_relation(first[3], second[3])
                self.assertEqual(got, want, (first[0], second[0]))
        return log

    def test_random_batches(self):
        rng = random.Random(1234)
        for _ in range(15):
            self.check_batch(random_events(rng, 25))

    def test_equal_clocks_are_incomparable(self):
        events = [
            ("a", "n0", 1, {"n0": 1, "n1": 2}),
            ("b", "n1", 2, {"n0": 1, "n1": 2}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.txt"
            write_events(path, events)
            log = core.parse(str(path))
        self.assertEqual(core.relate(log, 0, 1), core.INCOMP)
        self.assertEqual(core.relate(log, 1, 0), core.INCOMP)


class TotalOrderTest(unittest.TestCase):
    def test_matches_reference_and_respects_causality(self):
        rng = random.Random(99)
        for _ in range(15):
            events = random_events(rng, 30)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.txt"
                write_events(path, events)
                log = core.parse(str(path))
            perm = core.total_order(log)
            got_ids = [log.event_id(i).decode("ascii") for i in perm]
            want_ids = [event[0] for event in ref_order(events)]
            self.assertEqual(got_ids, want_ids)
            # 线性扩展：有因果关系的必然先因后果
            position = {eid: i for i, eid in enumerate(got_ids)}
            for first in events:
                for second in events:
                    if ref_relation(first[3], second[3]) == core.LT:
                        self.assertLess(position[first[0]], position[second[0]])

    def test_input_line_order_is_irrelevant(self):
        rng = random.Random(5)
        events = random_events(rng, 40)
        shuffled = list(events)
        rng.shuffle(shuffled)
        with tempfile.TemporaryDirectory() as tmp:
            path_a = Path(tmp) / "a.txt"
            path_b = Path(tmp) / "b.txt"
            write_events(path_a, events)
            write_events(path_b, shuffled)
            log_a = core.parse(str(path_a))
            log_b = core.parse(str(path_b))
            ids_a = [log_a.event_id(i) for i in core.total_order(log_a)]
            ids_b = [log_b.event_id(i) for i in core.total_order(log_b)]
        self.assertEqual(ids_a, ids_b)


if __name__ == "__main__":
    unittest.main()


class StreamingKeyTest(unittest.TestCase):
    def test_streaming_order_matches_array_order(self):
        rng = random.Random(2026)
        for _ in range(10):
            events = random_events(rng, 40)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.txt"
                write_events(path, events)
                keys = core.clock_keys_from_file(str(path))
                stream_ids = [core.key_id(k) for k in sorted(keys)]
                log = core.parse(str(path))
                array_ids = [log.event_id(i) for i in core.total_order(log)]
            self.assertEqual(stream_ids, array_ids)

    def test_key_id_roundtrip(self):
        rng = random.Random(3)
        events = random_events(rng, 30)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.txt"
            write_events(path, events)
            keys = core.clock_keys_from_file(str(path))
        got = sorted(core.key_id(k) for k in keys)
        want = sorted(event[0].encode("ascii") for event in events)
        self.assertEqual(got, want)
