"""page 子命令：把全序前若干条事件摊成页面数据（JSON）。"""

import json

from .core import LT, load_log, relate, total_order

DEFAULT_LIMIT = 400
INCOMPARABLE_LIMIT = 20


def build_page_data(log, limit):
    order = total_order(log)
    total = log.count
    shown = min(limit, total)
    visible = [order[k] for k in range(shown)]

    # 可见事件两两关系：lt[i] = {j | 第 i 条 < 第 j 条}（i、j 为全序位置）
    lt = [set() for _ in range(shown)]
    comparable = 0
    incomparable_pairs = []
    for i in range(shown):
        for j in range(i + 1, shown):
            rel = relate(log, visible[i], visible[j])
            if rel == LT:
                lt[i].add(j)
                comparable += 1
            elif rel == "GT":
                lt[j].add(i)
                comparable += 1
            elif len(incomparable_pairs) < INCOMPARABLE_LIMIT:
                incomparable_pairs.append(
                    [log.id_str(visible[i]), log.id_str(visible[j])])

    # 直接因果对：from 是 to 的因果前驱，且可见集合里没有 from < c < to，
    # 即 from 是 to 全部前驱中的极大元；按全序位置从后往前扫前驱即可。
    edges = []
    for j in range(shown):
        accepted = []
        for i in reversed([i for i in range(j) if j in lt[i]]):
            if not any(m in lt[i] for m in accepted):
                accepted.append(i)
                edges.append({"from": log.id_str(visible[i]),
                              "to": log.id_str(visible[j])})
    pos_of = {log.id_str(visible[k]): k + 1 for k in range(shown)}
    edges.sort(key=lambda e: (pos_of[e["from"]], pos_of[e["to"]]))

    lanes_by_node = {}
    for pos, idx in enumerate(visible, 1):
        node = log.nodes[idx]
        if node not in lanes_by_node:
            lanes_by_node[node] = pos
    lanes = [
        {"node": node, "first_pos": pos}
        for node, pos in sorted(lanes_by_node.items(), key=lambda kv: (kv[1], kv[0]))
    ]

    return {
        "total": total,
        "shown": shown,
        "limit": limit,
        "lanes": lanes,
        "events": [
            {
                "id": log.id_str(idx),
                "node": log.nodes[idx],
                "pos": pos,
                "wall": log.walls[idx],
                "clock": log.clock_pairs(idx),
            }
            for pos, idx in enumerate(visible, 1)
        ],
        "edges": edges,
        "stats": {
            "comparable_pairs": comparable,
            "incomparable_pairs": shown * (shown - 1) // 2 - comparable,
        },
        "incomparable": incomparable_pairs,
    }


def run_page(events_path, out_path, limit=DEFAULT_LIMIT):
    log = load_log(events_path)
    data = build_page_data(log, limit)
    with open(out_path, "w", encoding="ascii", newline="") as fh:
        json.dump(data, fh, ensure_ascii=True, separators=(",", ":"))
        fh.write("\n")
    return data["shown"]
