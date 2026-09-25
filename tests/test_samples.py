import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, ".")
from causalline.core import run_order, run_relate

SAMPLES = Path("samples")
CASES = ["chain", "fork", "parallel", "single", "skewed", "stale", "sparse", "scale"]


class SampleTest(unittest.TestCase):
    def run_case(self, case, tmp):
        events = SAMPLES / ("events-%s.txt" % case)
        pairs = SAMPLES / ("pairs-%s.txt" % case)
        out_order = tmp / ("o-%s.txt" % case)
        out_rel = tmp / ("r-%s.txt" % case)
        run_order(str(events), str(out_order))
        run_relate(str(events), str(pairs), str(out_rel))
        self.assertEqual(out_order.read_bytes(),
                         (SAMPLES / ("expected-%s.order.txt" % case)).read_bytes(),
                         "%s order" % case)
        self.assertEqual(out_rel.read_bytes(),
                         (SAMPLES / ("expected-%s.rel.txt" % case)).read_bytes(),
                         "%s relate" % case)

    def test_all_cases_byte_exact(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            for case in CASES:
                with self.subTest(case=case):
                    self.run_case(case, tmp)

    def test_shuffled_input_gives_same_output(self):
        import random
        rng = random.Random(42)
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            for case in ["fork", "stale", "skewed", "parallel"]:
                with self.subTest(case=case):
                    events = SAMPLES / ("events-%s.txt" % case)
                    lines = events.read_text().splitlines()
                    rng.shuffle(lines)
                    shuffled = tmp / ("shuf-%s.txt" % case)
                    shuffled.write_text("\n".join(lines) + "\n")
                    out_order = tmp / ("so-%s.txt" % case)
                    out_rel = tmp / ("sr-%s.txt" % case)
                    run_order(str(shuffled), str(out_order))
                    run_relate(str(shuffled), str(SAMPLES / ("pairs-%s.txt" % case)), str(out_rel))
                    self.assertEqual(out_order.read_bytes(),
                                     (SAMPLES / ("expected-%s.order.txt" % case)).read_bytes())
                    self.assertEqual(out_rel.read_bytes(),
                                     (SAMPLES / ("expected-%s.rel.txt" % case)).read_bytes())

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            proc = subprocess.run(
                [sys.executable, "-m", "causalline", "order",
                 "samples/events-fork.txt", str(out)],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out.read_bytes(),
                             Path("samples/expected-fork.order.txt").read_bytes())


if __name__ == "__main__":
    unittest.main()
