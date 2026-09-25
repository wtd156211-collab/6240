"""向量时钟的解析、压缩存储、因果判定与全序。

压缩口径（README 第 3 节）：时钟只存非零分量。需要随机访问时（relate/page），
全部事件的分量平铺在两条等长数组里（分量名序号 + 计数），事件只记录自己
分量区间的端点；只需要全序时（order）干脆不落数组，流式把每条时钟编成
保序 key。没有任何「事件数 x 节点数」的结构，判定语义不变。

全序 key 的构造（README 第 2 节的「时钟字典序 + id 破并列」）：

- 稠密字典序 = 两时钟在分量名并集上逐分量比计数，缺的按 0。等价地，把每条
  时钟表示成「按名字升序的分量序列」，逐位置比较：同一位置名字不同，则名字
  靠前者更大（对方在该名字上为 0）；名字相同比计数；一方序列先耗尽（是另一方
  的前缀）则更小。
- 为了让 bytes 比较天然实现上述规则，分量名逐字节取反（名字字符集取反后落在
  [133, 210]），于是「名字越靠前、编码越大」；名与计数之间用 0xff 分隔（大于
  任何取反字节，保证名字互为前缀时短名编码更大）；计数用保序变长编码 _enc。
- 时钟序列之后接 0x00 + id：0x00 小于任何分量编码的首字节，所以「短时钟更小」
  的前缀规则不会被 id 破坏；时钟完全相等时由 id 字节序定先后。
"""

from array import array

LT = "LT"
GT = "GT"
INCOMP = "INCOMP"

_INV_TABLE = bytes.maketrans(bytes(range(256)), bytes(255 - c for c in range(256)))
_NAME_SEP = b"\xff"
_ID_SEP = b"\x00"


def _enc(value):
    """非负整数的保序变长编码：首字节为字节数，随后是大端字节（前缀自由）。"""
    length = max(1, (value.bit_length() + 7) // 8)
    return bytes((length,)) + value.to_bytes(length, "big")


def key_id(key):
    """从全序 key 里取回事件 id（id 字符集不含 0x00，最后一个 0x00 即分隔符）。"""
    return key[key.rindex(_ID_SEP) + 1:]


def clock_keys_from_file(path):
    """流式读事件文件，返回每条事件的全序 key（bytes）列表，不落地任何数组。"""
    keys = []
    append = keys.append
    inv_cache = {}
    enc_cache = {}
    with open(path, "rb") as fh:
        for line in fh:
            eid, _, _, clock = line.split(b" ")
            parts = []
            parts_append = parts.append
            for raw in clock.split(b","):
                name, _, num = raw.partition(b":")
                inv = inv_cache.get(name)
                if inv is None:
                    inv = name.translate(_INV_TABLE)
                    inv_cache[name] = inv
                count = int(num)
                encoded = enc_cache.get(count)
                if encoded is None:
                    encoded = _enc(count)
                    enc_cache[count] = encoded
                parts_append(inv)
                parts_append(_NAME_SEP)
                parts_append(encoded)
            parts_append(_ID_SEP)
            parts_append(eid)
            append(b"".join(parts))
    return keys


class EventLog:
    """一批事件的列式存储。id_filter 过滤时只保留被需要的事件。"""

    __slots__ = ("ids", "id_off", "nodes", "walls", "comp", "cnt", "off",
                 "names", "index")

    def __init__(self):
        self.ids = bytearray()        # 所有 id 字节拼接
        self.id_off = array("Q", [0]) # 每条事件 id 在 ids 里的区间，N+1 个
        self.nodes = array("I")       # 每条事件的节点名序号（keep_meta 时才有）
        self.walls = array("Q")       # 每条事件的 wall 毫秒（keep_meta 时才有）
        self.comp = array("I")        # 所有时钟分量名序号，平铺
        self.cnt = array("I")         # 与 comp 等长的计数
        self.off = array("Q", [0])    # 每条事件分量区间端点，N+1 个
        self.names = []               # 分量名，按字节序升序
        self.index = None             # id_filter 时：id bytes -> 过滤后下标

    def __len__(self):
        return len(self.off) - 1

    def event_id(self, index):
        return bytes(self.ids[self.id_off[index]:self.id_off[index + 1]])


def parse(path, keep_meta=False, id_filter=None):
    """读事件文件，返回 EventLog。

    keep_meta=True 时额外保留 node/wall；id_filter 给定时只保留 id 在集合里
    的事件，并把「id -> 过滤后下标」放在 log.index。
    """
    log = EventLog()
    intern = {}
    tmp_names = []
    ids = log.ids
    id_off = log.id_off
    comp = log.comp
    cnt = log.cnt
    off = log.off
    nodes = log.nodes
    walls = log.walls
    index = {} if id_filter is not None else None
    with open(path, "rb") as fh:
        for line in fh:
            eid, node, wall, clock = line.split(b" ")
            if id_filter is not None:
                if eid not in id_filter:
                    continue
                index[eid] = len(off) - 1
            ids += eid
            id_off.append(len(ids))
            if keep_meta:
                idx = intern.get(node)
                if idx is None:
                    idx = len(tmp_names)
                    intern[node] = idx
                    tmp_names.append(node)
                nodes.append(idx)
                walls.append(int(wall))
            for token in clock.split(b","):
                name, _, num = token.partition(b":")
                idx = intern.get(name)
                if idx is None:
                    idx = len(tmp_names)
                    intern[name] = idx
                    tmp_names.append(name)
                comp.append(idx)
                cnt.append(int(num))
            off.append(len(comp))
    # 解析时的临时序号是插入序，重映射为名字字节序，后续比较与编码都用它
    order = sorted(range(len(tmp_names)), key=tmp_names.__getitem__)
    rank = [0] * len(tmp_names)
    names = [None] * len(tmp_names)
    for new_idx, old_idx in enumerate(order):
        rank[old_idx] = new_idx
        names[new_idx] = tmp_names[old_idx]
    log.names = names
    if len(tmp_names) > 1:
        log.comp = array("I", map(rank.__getitem__, log.comp))
        if keep_meta:
            log.nodes = array("I", map(rank.__getitem__, log.nodes))
    log.index = index
    return log


def relate(log, a, b):
    """事件 a、b 的因果关系：LT / GT / INCOMP（时钟相等也算 INCOMP）。

    两条稀疏分量序列的归并扫描，代价只与两时钟长度有关，与事件总数无关。
    """
    comp = log.comp
    cnt = log.cnt
    off = log.off
    i, j = off[a], off[b]
    end_i, end_j = off[a + 1], off[b + 1]
    less = greater = False
    while i < end_i and j < end_j:
        name_a = comp[i]
        name_b = comp[j]
        if name_a == name_b:
            val_a = cnt[i]
            val_b = cnt[j]
            if val_a < val_b:
                less = True
            elif val_a > val_b:
                greater = True
            i += 1
            j += 1
        elif name_a < name_b:
            greater = True  # a 有的分量 b 没有：该分量上 a > b(=0)
            i += 1
        else:
            less = True
            j += 1
        if less and greater:
            return INCOMP
    if i < end_i:
        greater = True
    elif j < end_j:
        less = True
    if less:
        return INCOMP if greater else LT
    return GT if greater else INCOMP


def order_keys(log):
    """每条事件的全序 key（bytes），与 clock_keys_from_file 同口径。"""
    inv_cache = {}
    enc_cache = {}
    names = log.names
    comp = log.comp
    cnt = log.cnt
    off = log.off
    ids = log.ids
    id_off = log.id_off
    keys = []
    append = keys.append
    for event in range(len(log)):
        parts = []
        parts_append = parts.append
        for p in range(off[event], off[event + 1]):
            name = names[comp[p]]
            inv = inv_cache.get(name)
            if inv is None:
                inv = name.translate(_INV_TABLE)
                inv_cache[name] = inv
            count = cnt[p]
            encoded = enc_cache.get(count)
            if encoded is None:
                encoded = _enc(count)
                enc_cache[count] = encoded
            parts_append(inv)
            parts_append(_NAME_SEP)
            parts_append(encoded)
        parts_append(_ID_SEP)
        parts_append(ids[id_off[event]:id_off[event + 1]])
        append(b"".join(parts))
    return keys


def total_order(log):
    """返回全序下标序列：第 1 位是全序第 1 位的事件下标。"""
    keys = order_keys(log)
    return sorted(range(len(log)), key=keys.__getitem__)
