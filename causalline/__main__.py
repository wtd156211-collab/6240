"""命令行入口：

    python -m causalline order  <事件> <全序>
    python -m causalline relate <事件> <清单> <关系>
    python -m causalline page   <事件> <json> [条数]
"""

import json
import sys
import time

from . import core
from . import page as _page


def _stderr(message):
    sys.stderr.write(message + "\n")


def _cmd_order(events_path, out_path):
    start = time.monotonic()
    keys = core.clock_keys_from_file(events_path)
    keys.sort()
    with open(out_path, "wb") as fh:
        chunk = []
        for key in keys:
            chunk.append(core.key_id(key))
            if len(chunk) >= 65536:
                fh.write(b"\n".join(chunk) + b"\n")
                chunk.clear()
        if chunk:
            fh.write(b"\n".join(chunk) + b"\n")
    _stderr("order: %d events -> %s (%.2fs)"
            % (len(keys), out_path, time.monotonic() - start))


def _cmd_relate(events_path, pairs_path, out_path):
    start = time.monotonic()
    with open(pairs_path, "rb") as src:
        pairs = [line.split() for line in src]
    needed = set()
    for pair in pairs:
        needed.update(pair)
    log = core.parse(events_path, id_filter=needed)
    index = log.index
    with open(out_path, "wb") as out:
        for id_a, id_b in pairs:
            rel = core.relate(log, index[id_a], index[id_b])
            out.write(id_a + b" " + id_b + b" " + rel.encode("ascii") + b"\n")
    _stderr("relate: %d queries over %d events -> %s (%.2fs)"
            % (len(pairs), len(log), out_path, time.monotonic() - start))


def _cmd_page(events_path, json_path, limit):
    start = time.monotonic()
    keys = core.clock_keys_from_file(events_path)
    keys.sort()
    total = len(keys)
    visible_ids = [core.key_id(key) for key in keys[:min(limit, total)]]
    del keys
    log = core.parse(events_path, keep_meta=True, id_filter=set(visible_ids))
    data = _page.build(log, visible_ids, total, limit)
    with open(json_path, "w", encoding="ascii", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=True)
        fh.write("\n")
    _stderr("page: %d events, shown %d -> %s (%.2fs)"
            % (total, data["shown"], json_path, time.monotonic() - start))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = ("usage: python -m causalline order <events> <out> | "
             "relate <events> <pairs> <out> | page <events> <json> [limit]")
    if not argv:
        _stderr(usage)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "order" and len(args) == 2:
        _cmd_order(*args)
    elif cmd == "relate" and len(args) == 3:
        _cmd_relate(*args)
    elif cmd == "page" and len(args) in (2, 3):
        _cmd_page(args[0], args[1], int(args[2]) if len(args) == 3 else 400)
    else:
        _stderr(usage)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
