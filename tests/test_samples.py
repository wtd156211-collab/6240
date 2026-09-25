"""对照 samples/ 的期望输出逐字节校验，并检查确定性。"""

import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
CASES = ["chain", "fork", "parallel", "single", "skewed", "stale", "sparse", "scale"]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "causalline", *args],
        cwd=ROOT, check=True, capture_output=True,
    )


class SampleOrderTest(unittest.TestCase):
    def check_case(self, case):
        events = SAMPLES / ("events-%s.txt" % case)
        pairs = SAMPLES / ("pairs-%s.txt" % case)
        want_order = (SAMPLES / ("expected-%s.order.txt" % case)).read_bytes()
        want_rel = (SAMPLES / ("expected-%s.rel.txt" % case)).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out_order = Path(tmp) / "order.txt"
            out_rel = Path(tmp) / "rel.txt"
            run_cli("order", str(events), str(out_order))
            run_cli("relate", str(events), str(pairs), str(out_rel))
            self.assertEqual(out_order.read_bytes(), want_order)
            self.assertEqual(out_rel.read_bytes(), want_rel)


for _case in CASES:
    def _make(case):
        def test(self):
            self.check_case(case)
        return test
    setattr(SampleOrderTest, "test_%s" % _case, _make(_case))


class DeterminismTest(unittest.TestCase):
    def test_same_input_twice_same_output(self):
        events = SAMPLES / "events-scale.txt"
        with tempfile.TemporaryDirectory() as tmp:
            out_a = Path(tmp) / "a.txt"
            out_b = Path(tmp) / "b.txt"
            run_cli("order", str(events), str(out_a))
            run_cli("order", str(events), str(out_b))
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())

    def test_shuffled_input_same_output(self):
        for case in ("fork", "stale", "skewed"):
            events = SAMPLES / ("events-%s.txt" % case)
            pairs = SAMPLES / ("pairs-%s.txt" % case)
            lines = events.read_text(encoding="ascii").splitlines()
            random.Random(42).shuffle(lines)
            with tempfile.TemporaryDirectory() as tmp:
                shuffled = Path(tmp) / "events.txt"
                shuffled.write_text("\n".join(lines) + "\n", encoding="ascii")
                out_order = Path(tmp) / "order.txt"
                out_rel = Path(tmp) / "rel.txt"
                run_cli("order", str(shuffled), str(out_order))
                run_cli("relate", str(shuffled), str(pairs), str(out_rel))
                want_order = (SAMPLES / ("expected-%s.order.txt" % case)).read_bytes()
                want_rel = (SAMPLES / ("expected-%s.rel.txt" % case)).read_bytes()
                self.assertEqual(out_order.read_bytes(), want_order, case)
                self.assertEqual(out_rel.read_bytes(), want_rel, case)


if __name__ == "__main__":
    unittest.main()
