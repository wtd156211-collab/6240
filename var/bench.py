import tracemalloc, time
from causalline import core

tracemalloc.start()
t0 = time.monotonic()
keys = core.clock_keys_from_file("var/events-3m.txt")
keys.sort()
ids = [core.key_id(k) for k in keys[:5]]
peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
elapsed = time.monotonic() - t0
print("order-path: events=%d elapsed=%.1fs peak=%.1fMiB (limit 512MiB) -> %s"
      % (len(keys), elapsed, peak / 2**20, "OK" if peak <= 512 * 2**20 else "OVER"))
print("first ids:", ids)
