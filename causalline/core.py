"""向量时钟与因果排序核心。

常驻表示（EventLog）是稀疏且定长的：
- 分量名全批共享一张名字表（按字节序升序），事件里只存名字的整数编号；
- 所有事件的分量摊平进两个等长 array：crank（编号，4 字节）+ ccount
  （计数，8 字节），每个分量 12 字节，只存非零分量；
- 每条事件只存分量区间偏移（coff，8 字节）等定长字段，id 全部拼进一个
  bytes 块加偏移数组。
没有「事件数 x 节点数」量级的结构，不裁剪任何非零分量，因此压缩前后每
一对事件的判定结果完全相同。关系判定是两个分量区间的归并，代价只与两
个时钟的分量数有关，与事件总数无关。
"""

import sys
from array import array

LT = "LT"
GT = "GT"
INCOMP = "INCOMP"


class EventLog:
    """一批事件的紧凑表示。下标 i 即事件在批内的序号。"""

    __slots__ = ("names", "crank", "ccount", "coff",
                 "ids", "id_off", "nodes", "walls")

    def __init__(self):
        self.names = []          # 分量名表，按字节序升序；编号 = 下标
        self.crank = array("I")  # 全事件分量名编号，摊平
        self.ccount = array("Q")  # 与 crank 等长的计数
        self.coff = array("Q", [0])  # 事件 i 的分量区间 [coff[i], coff[i+1])
        self.ids = b""           # 全部 id 拼接
        self.id_off = array("Q", [0])
        self.nodes = []          # 每条事件的节点名（intern 共享）
        self.walls = array("Q")

    @property
    def count(self):
        return len(self.walls)

    def id_bytes(self, i):
        return self.ids[self.id_off[i]:self.id_off[i + 1]]

    def id_str(self, i):
        return self.id_bytes(i).decode("ascii")

    def clock_pairs(self, i):
        return [[self.names[self.crank[k]], self.ccount[k]]
                for k in range(self.coff[i], self.coff[i + 1])]


def _parse_clock(text):
    # 'a:1,b:2' -> (('a', 1), ('b', 2))；输入保证合法、按名字升序
    parts = []
    for seg in text.split(","):
        name, _, count = seg.partition(":")
        parts.append((name, int(count)))
    return parts


def build_log(rows):
    """由 (id, node, wall, clock) 行构造 EventLog。clock 为 (名字, 计数) 序列。"""
    log = EventLog()
    rank_of = {}
    crank = array("I")
    ccount = array("Q")
    coff = array("Q", [0])
    ids = bytearray()
    id_off = array("Q", [0])
    nodes = []
    walls = array("Q")
    for eid, node, wall, clock in rows:
        ids += eid.encode("ascii")
        id_off.append(len(ids))
        nodes.append(sys.intern(node))
        walls.append(wall)
        for name, cnt in clock:
            rank = rank_of.get(name)
            if rank is None:
                rank = len(rank_of)
                rank_of[name] = rank
            crank.append(rank)
            ccount.append(cnt)
        coff.append(len(crank))
    # 编号按名字字节序重排，使编号序 == 名字字节序
    names = sorted(rank_of)
    perm = [0] * len(names)
    for new_rank, name in enumerate(names):
        perm[rank_of[name]] = new_rank
    if names:
        crank = array("I", (perm[r] for r in crank))
    log.names = names
    log.crank = crank
    log.ccount = ccount
    log.coff = coff
    log.ids = bytes(ids)
    log.id_off = id_off
    log.nodes = nodes
    log.walls = walls
    return log


def load_log(path):
    def rows():
        with open(path, "r", encoding="ascii", newline="") as fh:
            for line in fh:
                eid, node, wall, clock = line.rstrip("\n").split(" ")
                yield eid, node, int(wall), _parse_clock(clock)

    return build_log(rows())


def relate(log, i, j):
    """分量级偏序：i < j 返回 LT，j < i 返回 GT，其余（含相等）INCOMP。"""
    crank = log.crank
    ccount = log.ccount
    coff = log.coff
    p, pe = coff[i], coff[i + 1]
    q, qe = coff[j], coff[j + 1]
    a_less = a_greater = False
    while p < pe and q < qe:
        rp = crank[p]
        rq = crank[q]
        if rp == rq:
            cp = ccount[p]
            cq = ccount[q]
            if cp < cq:
                a_less = True
            elif cp > cq:
                a_greater = True
            p += 1
            q += 1
        elif rp < rq:
            a_greater = True  # i 在该分量 > 0，j 为 0
            p += 1
        else:
            a_less = True
            q += 1
        if a_less and a_greater:
            return INCOMP
    if p < pe:
        a_greater = True
    elif q < qe:
        a_less = True
    if a_less and a_greater:
        return INCOMP
    if a_less:
        return LT
    if a_greater:
        return GT
    return INCOMP  # 两时钟完全相同


def lex_compare(log, i, j):
    """时钟字典序：分量名并集按字节序逐项比计数（缺为 0），首个不相等定先后。"""
    crank = log.crank
    ccount = log.ccount
    coff = log.coff
    p, pe = coff[i], coff[i + 1]
    q, qe = coff[j], coff[j + 1]
    while p < pe and q < qe:
        rp = crank[p]
        rq = crank[q]
        if rp == rq:
            cp = ccount[p]
            cq = ccount[q]
            if cp != cq:
                return -1 if cp < cq else 1
            p += 1
            q += 1
        elif rp < rq:
            return 1  # j 在该分量为 0，i 为正
        else:
            return -1
    if p < pe:
        return 1
    if q < qe:
        return -1
    return 0


def total_order(log):
    """全序：排序键 (时钟字典序, id 字节序)，返回事件下标的 array。

    按 (下一个分量名, 该名计数) 多路分桶：同一桶的事件在已比较的所
    有分量上完全一致，桶间次序由字典序规则唯一确定（见下），桶内递
    归。每个事件每轮消耗自己的一个分量，总代价 O(分量总数)，不做事
    件数平方量级的两两比较。结果只依赖事件本身，与读入行序无关。
    """
    n = log.count
    out = array("I")
    if n == 0:
        return out
    crank = log.crank
    ccount = log.ccount
    coff = log.coff
    ptr = array("I", [0]) * n  # 每个事件下一个待比较的分量（事件内偏移）
    id_bytes = log.id_bytes
    stack = [array("I", range(n))]
    while stack:
        group = stack.pop()
        if len(group) == 1:
            out.append(group[0])
            continue
        buckets = {}
        min_name = None
        for i in group:
            p = coff[i] + ptr[i]
            if p < coff[i + 1]:
                key = (crank[p], ccount[p])
                ptr[i] = ptr[i] + 1
                if min_name is None or key[0] < min_name:
                    min_name = key[0]
            else:
                key = None  # 时钟已耗尽：剩余分量全 0
            bucket = buckets.get(key)
            if bucket is None:
                buckets[key] = bucket = array("I")
            bucket.append(i)
        if len(buckets) == 1:
            only = next(iter(buckets))
            if only is None:
                # 整组时钟完全相同，按 id 字节序破并列
                out.extend(sorted(group, key=id_bytes))
            else:
                stack.append(group)
            continue
        # 桶间次序（m0 = 本组最小分歧分量名）：
        # - 耗尽桶（None）：剩余全 0，最小；
        # - 名字大于 m0 的桶：在 m0 上计数为 0，先于任何 m0 桶；相互之间
        #   名字大的在前（名字小者在对方的名字上为 0 < 正计数），同名按
        #   计数升序；
        # - m0 桶：按计数升序。
        def bucket_order(key):
            if key is None:
                return (0, 0, 0)
            if key[0] == min_name:
                return (2, 0, key[1])
            return (1, -key[0], key[1])

        for key in sorted(buckets, key=bucket_order, reverse=True):
            stack.append(buckets[key])
    return out


def run_order(events_path, out_path):
    log = load_log(events_path)
    order = total_order(log)
    ids = log.ids
    off = log.id_off
    with open(out_path, "wb") as fh:
        write = fh.write
        for i in order:
            write(ids[off[i]:off[i + 1]])
            write(b"\n")
    return log.count


def run_relate(events_path, pairs_path, out_path):
    log = load_log(events_path)
    index = {log.id_bytes(i): i for i in range(log.count)}
    count = 0
    with open(pairs_path, "r", encoding="ascii", newline="") as src, \
            open(out_path, "wb") as dst:
        for line in src:
            a_id, b_id = line.rstrip("\n").split(" ")
            rel = relate(log, index[a_id.encode("ascii")],
                         index[b_id.encode("ascii")])
            dst.write(("%s %s %s\n" % (a_id, b_id, rel)).encode("ascii"))
            count += 1
    return count
