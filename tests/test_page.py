import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, ".")
from causalline.core import LT, load_log, relate
from causalline.pagedata import build_page_data


class PageDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = load_log("samples/events-fork.txt")
        cls.data = build_page_data(cls.log, 400)

    def test_fixed_keys_and_counts(self):
        d = self.data
        self.assertEqual(set(d), {"total", "shown", "limit", "lanes", "events",
                                  "edges", "stats", "incomparable"})
        self.assertEqual(d["total"], self.log.count)
        self.assertEqual(d["shown"], min(400, d["total"]))
        self.assertEqual(d["limit"], 400)
        shown = d["shown"]
        self.assertEqual(len(d["events"]), shown)
        self.assertEqual([e["pos"] for e in d["events"]], list(range(1, shown + 1)))
        s = d["stats"]
        self.assertEqual(s["comparable_pairs"] + s["incomparable_pairs"],
                         shown * (shown - 1) // 2)

    def test_lanes_sorted_by_first_pos(self):
        lanes = self.data["lanes"]
        keys = [(l["first_pos"], l["node"]) for l in lanes]
        self.assertEqual(keys, sorted(keys))
        lane_nodes = {l["node"] for l in lanes}
        self.assertEqual(lane_nodes, {e["node"] for e in self.data["events"]})
        for l in lanes:
            firsts = [e["pos"] for e in self.data["events"] if e["node"] == l["node"]]
            self.assertEqual(l["first_pos"], min(firsts))

    def test_edges_are_direct_causal_pairs(self):
        d = self.data
        index = {self.log.id_str(i): i for i in range(self.log.count)}
        pos = {e["id"]: e["pos"] for e in d["events"]}
        for edge in d["edges"]:
            a, b = edge["from"], edge["to"]
            self.assertLess(pos[a], pos[b])
            self.assertEqual(relate(self.log, index[a], index[b]), LT)
            # 可见集合里不存在 c 使 a < c < b
            for c_id in pos:
                if c_id in (a, b):
                    continue
                self.assertFalse(
                    relate(self.log, index[a], index[c_id]) == LT
                    and relate(self.log, index[c_id], index[b]) == LT,
                    "%s < %s < %s" % (a, c_id, b))
        edge_keys = [(pos[e["from"]], pos[e["to"]]) for e in d["edges"]]
        self.assertEqual(edge_keys, sorted(edge_keys))

    def test_incomparable_pairs(self):
        d = self.data
        index = {self.log.id_str(i): i for i in range(self.log.count)}
        pos = {e["id"]: e["pos"] for e in d["events"]}
        self.assertLessEqual(len(d["incomparable"]), 20)
        keys = []
        for a, b in d["incomparable"]:
            self.assertLess(pos[a], pos[b])
            self.assertEqual(relate(self.log, index[a], index[b]), "INCOMP")
            keys.append((pos[a], pos[b]))
        self.assertEqual(keys, sorted(keys))
        # 数量与 stats 对得上（可见对不足 20 时）
        if d["stats"]["incomparable_pairs"] <= 20:
            self.assertEqual(len(d["incomparable"]), d["stats"]["incomparable_pairs"])

    def test_limit_is_respected(self):
        d = build_page_data(self.log, 4)
        self.assertEqual(d["shown"], 4)
        self.assertEqual(len(d["events"]), 4)

    def test_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data.json"
            proc = subprocess.run(
                [sys.executable, "-m", "causalline", "page",
                 "samples/events-fork.txt", str(out), "400"],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            d = json.loads(out.read_text())
            self.assertEqual(d["total"], 10)
            self.assertEqual(d["shown"], 10)


class PageScaleTest(unittest.TestCase):
    def test_scale_page(self):
        log = load_log("samples/events-scale.txt")
        d = build_page_data(log, 400)
        self.assertEqual(d["shown"], 400)
        s = d["stats"]
        self.assertEqual(s["comparable_pairs"] + s["incomparable_pairs"], 400 * 399 // 2)


if __name__ == "__main__":
    unittest.main()
