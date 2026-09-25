import random
import sys
import unittest
from functools import cmp_to_key

sys.path.insert(0, ".")
from causalline.core import (INCOMP, LT, GT, build_log, load_log, lex_compare,
                             relate, total_order)


def dense_relate(a, b, names):
    da, db = dict(a), dict(b)
    a_less = a_greater = False
    for n in names:
        ca, cb = da.get(n, 0), db.get(n, 0)
        a_less |= ca < cb
        a_greater |= ca > cb
    if a_less and a_greater:
        return INCOMP
    if a_less:
        return LT
    if a_greater:
        return GT
    return INCOMP


def dense_lex(a, b, names):
    da, db = dict(a), dict(b)
    for n in names:
        ca, cb = da.get(n, 0), db.get(n, 0)
        if ca != cb:
            return -1 if ca < cb else 1
    return 0


def rand_clock(rng, names, max_components=4):
    picked = sorted(rng.sample(names, rng.randint(1, min(max_components, len(names)))))
    return tuple((n, rng.randint(1, 9)) for n in picked)


def make_log(events):
    return build_log([(eid, node, wall, clock) for eid, node, wall, clock in events])


class RelateTest(unittest.TestCase):
    def one(self, a, b):
        log = make_log([("e1", "n1", 0, a), ("e2", "n2", 0, b)])
        return relate(log, 0, 1)

    def test_basic_relations(self):
        a = (("n1", 1), ("n2", 2))
        b = (("n1", 1), ("n2", 3))
        self.assertEqual(self.one(a, b), LT)
        self.assertEqual(self.one(b, a), GT)

    def test_equal_clocks_are_incomparable(self):
        a = (("n1", 2), ("n2", 2))
        self.assertEqual(self.one(a, a), INCOMP)

    def test_divergent_clocks_are_incomparable(self):
        self.assertEqual(self.one((("n1", 2),), (("n2", 1),)), INCOMP)
        self.assertEqual(self.one((("n2", 1),), (("n1", 2),)), INCOMP)

    def test_missing_components_count_as_zero(self):
        self.assertEqual(self.one((("n1", 1),), (("n1", 1), ("n9", 1))), LT)

    def test_random_against_dense_reference(self):
        rng = random.Random(20260925)
        names = ["n%03d" % i for i in range(30)]
        for _ in range(2000):
            a = rand_clock(rng, names)
            b = rand_clock(rng, names)
            log = make_log([("e1", "n1", 0, a), ("e2", "n2", 0, b)])
            self.assertEqual(relate(log, 0, 1), dense_relate(a, b, names))
            self.assertEqual(lex_compare(log, 0, 1), dense_lex(a, b, names))


class TotalOrderTest(unittest.TestCase):
    def reference_order(self, events, names):
        def cmp(i, j):
            c = dense_lex(events[i][3], events[j][3], names)
            if c:
                return c
            return (events[i][0] > events[j][0]) - (events[i][0] < events[j][0])
        return sorted(range(len(events)), key=cmp_to_key(cmp))

    def test_matches_reference_on_random_sets(self):
        rng = random.Random(7)
        names = ["n%02d" % i for i in range(12)]
        for trial in range(60):
            count = rng.randint(1, 60)
            events = [("e%03d" % i, rng.choice(names), rng.randint(0, 10**6),
                       rand_clock(rng, names, 5)) for i in range(count)]
            # 故意塞入时钟完全相同的事件，验证 id 破并列
            if count >= 3:
                events[1] = (events[1][0], events[1][1], 0, events[0][3])
                events[2] = (events[2][0], events[2][1], 0, events[0][3])
            log = make_log(events)
            got = [log.id_str(i) for i in total_order(log)]
            want = [events[i][0] for i in self.reference_order(events, names)]
            self.assertEqual(got, want, "trial %d" % trial)

    def test_input_line_order_is_irrelevant(self):
        rng = random.Random(11)
        names = ["n%02d" % i for i in range(8)]
        events = [("e%02d" % i, rng.choice(names), 0, rand_clock(rng, names))
                  for i in range(40)]
        base = [make_log(events).id_str(i) for i in total_order(make_log(events))]
        for _ in range(5):
            shuffled = events[:]
            rng.shuffle(shuffled)
            log = make_log(shuffled)
            got = [log.id_str(i) for i in total_order(log)]
            self.assertEqual(got, base)

    def test_linear_extension_property(self):
        # e < f 的事件必排在 f 前面
        rng = random.Random(3)
        names = ["n%02d" % i for i in range(10)]
        events = [("e%02d" % i, rng.choice(names), 0, rand_clock(rng, names))
                  for i in range(80)]
        log = make_log(events)
        order = total_order(log)
        pos = {idx: p for p, idx in enumerate(order)}
        for i in range(len(events)):
            for j in range(len(events)):
                if relate(log, i, j) == LT:
                    self.assertLess(pos[i], pos[j])


class CompressionTest(unittest.TestCase):
    def test_storage_is_sparse_and_exact(self):
        # 常驻表示只含非零分量，且与原文逐分量一致（压缩不改语义）
        log = load_log("samples/events-sparse.txt")
        total_components = len(log.crank)
        self.assertEqual(total_components, len(log.ccount))
        self.assertEqual(total_components, log.coff[log.count])
        self.assertLessEqual(total_components, 4 * log.count)  # 每条只有 2-4 个分量
        self.assertEqual(log.names, sorted(log.names))
        for i in range(log.count):
            pairs = log.clock_pairs(i)
            self.assertLessEqual(len(pairs), 4)  # 不是节点数等宽的向量
            self.assertEqual([n for n, _ in pairs], sorted(n for n, _ in pairs))
            for _n, cnt in pairs:
                self.assertGreaterEqual(cnt, 1)  # 只存非零分量
            # 时钟必须含本事件 node 的分量
            self.assertIn(log.nodes[i], [n for n, _ in pairs])

    def test_component_names_shared(self):
        # 分量名全批共享一张表，事件里只存整数编号
        log = load_log("samples/events-scale.txt")
        self.assertLessEqual(len(log.names), 80)
        self.assertEqual(len(set(log.names)), len(log.names))


if __name__ == "__main__":
    unittest.main()
