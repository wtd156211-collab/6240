"""命令行入口：

    python -m causalline order  <事件> <全序>
    python -m causalline relate <事件> <清单> <关系>
    python -m causalline page   <事件> <json> [条数]
"""

import sys
import time

from .core import run_order, run_relate
from .pagedata import DEFAULT_LIMIT, run_page

USAGE = __doc__


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("order", "relate", "page"):
        sys.stderr.write(USAGE or "")
        return 2
    cmd = argv[0]
    started = time.monotonic()
    if cmd == "order" and len(argv) == 3:
        n = run_order(argv[1], argv[2])
    elif cmd == "relate" and len(argv) == 4:
        n = run_relate(argv[1], argv[2], argv[3])
    elif cmd == "page" and len(argv) in (3, 4):
        limit = int(argv[3]) if len(argv) == 4 else DEFAULT_LIMIT
        n = run_page(argv[1], argv[2], limit)
    else:
        sys.stderr.write(USAGE or "")
        return 2
    elapsed = time.monotonic() - started
    sys.stderr.write("%s: %d 条，%.3f 秒\n" % (cmd, n, elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
