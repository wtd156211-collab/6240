import tracemalloc, time, json
from causalline import core, page as pagemod

# relate 路径
tracemalloc.start()
t0 = time.monotonic()
with open("var/pairs-3m.txt", "rb") as src:
    pairs = [line.split() for line in src]
needed = set()
for p in pairs:
    needed.update(p)
log = core.parse("var/events-3m.txt", id_filter=needed)
rels = [core.relate(log, log.index[a], log.index[b]) for a, b in pairs]
peak1 = tracemalloc.get_traced_memory()[1]
t1 = time.monotonic() - t0
del log
# page 路径
keys = core.clock_keys_from_file("var/events-3m.txt")
keys.sort()
visible_ids = [core.key_id(k) for k in keys[:400]]
del keys
log = core.parse("var/events-3m.txt", keep_meta=True, id_filter=set(visible_ids))
data = pagemod.build(log, visible_ids, 3000000, 400)
peak2 = tracemalloc.get_traced_memory()[1]
t2 = time.monotonic() - t0
tracemalloc.stop()
print("relate: %.1fs peak-of-relate=%.1fMiB rels=%s" % (t1, peak1/2**20, {r: rels.count(r) for r in set(rels)}))
print("page:   %.1fs total-peak=%.1fMiB shown=%d edges=%d" % (t2, peak2/2**20, data["shown"], len(data["edges"])))
