"""page 子命令的 JSON 口径：结构、统计、直接因果边都对照朴素重算。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


def run_page(events, out, *extra):
    subprocess.run(
        [sys.executable, "-m", "causalline", "page", str(events), str(out), *extra],
        cwd=ROOT, check=True, capture_output=True,
    )


def relation(clock_a, clock_b):
    a = dict(clock_a)
    b = dict(clock_b)
    less = greater = False
    for name in set(a) | set(b):
        if a.get(name, 0) < b.get(name, 0):
            less = True
        elif a.get(name, 0) > b.get(name, 0):
            greater = True
    if less and greater:
        return "INCOMP"
    if less:
        return "LT"
    if greater:
        return "GT"
    return "INCOMP"


class PageTest(unittest.TestCase):
    def load(self, case, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data.json"
            run_page(SAMPLES / ("events-%s.txt" % case), out, *extra)
            return json.loads(out.read_text(encoding="ascii"))

    def test_structure_and_stats(self):
        data = self.load("fork")
        self.assertEqual(
            list(data),
            ["total", "shown", "limit", "lanes", "events", "edges",
             "stats", "incomparable"],
        )
        self.assertEqual(data["total"], 10)
        self.assertEqual(data["shown"], 10)
        self.assertEqual(data["limit"], 400)
        shown = data["shown"]
        self.assertEqual(
            data["stats"]["comparable_pairs"] + data["stats"]["incomparable_pairs"],
            shown * (shown - 1) // 2,
        )
        # pos 从 1 起、连续
        self.assertEqual([e["pos"] for e in data["events"]],
                         list(range(1, shown + 1)))
        # 泳道按 first_pos 升序
        firsts = [lane["first_pos"] for lane in data["lanes"]]
        self.assertEqual(firsts, sorted(firsts))
        lane_nodes = {lane["node"] for lane in data["lanes"]}
        self.assertEqual(lane_nodes, {e["node"] for e in data["events"]})

    def test_edges_are_direct_causal_pairs(self):
        data = self.load("fork")
        events = data["events"]
        clocks = {e["pos"]: e["clock"] for e in events}
        shown = data["shown"]
        want_edges = set()
        for a in range(1, shown + 1):
            for b in range(a + 1, shown + 1):
                if relation(clocks[a], clocks[b]) != "LT":
                    continue
                direct = not any(
                    relation(clocks[a], clocks[c]) == "LT"
                    and relation(clocks[c], clocks[b]) == "LT"
                    for c in range(1, shown + 1)
                    if c not in (a, b)
                )
                if direct:
                    want_edges.add((a, b))
        got_edges = {(edge["from"], edge["to"]) for edge in data["edges"]}
        self.assertEqual(got_edges, want_edges)
        self.assertEqual(
            [(e["from"], e["to"]) for e in data["edges"]],
            sorted(got_edges),
        )

    def test_stats_and_incomparable_list(self):
        data = self.load("fork")
        events = data["events"]
        clocks = {e["pos"]: e["clock"] for e in events}
        ids = {e["pos"]: e["id"] for e in events}
        shown = data["shown"]
        comparable = incomparable = 0
        want_list = []
        for a in range(1, shown + 1):
            for b in range(a + 1, shown + 1):
                if relation(clocks[a], clocks[b]) == "LT":
                    comparable += 1
                else:
                    incomparable += 1
                    if len(want_list) < 20:
                        want_list.append([ids[a], ids[b]])
        self.assertEqual(data["stats"]["comparable_pairs"], comparable)
        self.assertEqual(data["stats"]["incomparable_pairs"], incomparable)
        self.assertEqual(data["incomparable"], want_list)

    def test_limit_caps_shown(self):
        data = self.load("scale", "400")
        self.assertEqual(data["shown"], 400)
        self.assertEqual(data["total"], 40000)
        self.assertEqual(len(data["events"]), 400)
        self.assertEqual(len(data["incomparable"]), 20)

    def test_shown_is_min_of_limit_and_total(self):
        data = self.load("single", "1000")
        self.assertEqual(data["shown"], 9)
        self.assertEqual(data["limit"], 1000)


if __name__ == "__main__":
    unittest.main()
