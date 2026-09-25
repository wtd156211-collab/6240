"""page 子命令：把全序前若干条事件摊成页面用的 JSON（口径见 README 4.4）。"""

from . import core


def build(log, visible_ids, total, limit):
    """log 只含可见事件（parse 的 id_filter 过滤），visible_ids 按全序排列。"""
    shown = len(visible_ids)
    visible = [log.index[eid] for eid in visible_ids]
    names = log.names
    comp = log.comp
    cnt = log.cnt
    off = log.off

    # 泳道：只列有可见事件的节点，按各自最早可见事件的全序位置升序
    first_pos = {}
    for pos0, event in enumerate(visible):
        node = log.nodes[event]
        if node not in first_pos:
            first_pos[node] = pos0 + 1
    lane_items = sorted(first_pos.items(), key=lambda kv: (kv[1], names[kv[0]]))
    lanes = [
        {"node": names[node].decode("ascii"), "first_pos": pos}
        for node, pos in lane_items
    ]

    events = []
    for pos0, event in enumerate(visible):
        clock = [
            [names[comp[p]].decode("ascii"), cnt[p]]
            for p in range(off[event], off[event + 1])
        ]
        events.append({
            "id": log.event_id(event).decode("ascii"),
            "node": names[log.nodes[event]].decode("ascii"),
            "pos": pos0 + 1,
            "wall": log.walls[event],
            "clock": clock,
        })

    # 可见事件两两因果关系，存成每个事件的前驱位图
    pred = [0] * shown
    for b in range(shown):
        event_b = visible[b]
        bits = 0
        for a in range(b):
            if core.relate(log, visible[a], event_b) == core.LT:
                bits |= 1 << a
        pred[b] = bits

    # 直接因果对（可见事件上的传递约简）：a<b 且没有可见的 c 使 a<c<b
    edges = []
    for b in range(shown):
        covered = 0
        rest = pred[b]
        while rest:
            lsb = rest & -rest
            covered |= pred[lsb.bit_length() - 1]
            rest ^= lsb
        direct = pred[b] & ~covered
        while direct:
            lsb = direct & -direct
            edges.append({"from": lsb.bit_length(), "to": b + 1})
            direct ^= lsb
    edges.sort(key=lambda edge: (edge["from"], edge["to"]))

    comparable = sum(bits.bit_count() for bits in pred)
    total_pairs = shown * (shown - 1) // 2
    ids = [event["id"] for event in events]
    incomparable = []
    for a in range(shown):
        for b in range(a + 1, shown):
            if not (pred[b] >> a) & 1:
                incomparable.append([ids[a], ids[b]])
                if len(incomparable) >= 20:
                    break
        if len(incomparable) >= 20:
            break

    return {
        "total": total,
        "shown": shown,
        "limit": limit,
        "lanes": lanes,
        "events": events,
        "edges": edges,
        "stats": {
            "comparable_pairs": comparable,
            "incomparable_pairs": total_pairs - comparable,
        },
        "incomparable": incomparable,
    }
