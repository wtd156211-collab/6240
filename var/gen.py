import random, sys
n_events = int(sys.argv[1]); n_nodes = int(sys.argv[2]); out = sys.argv[3]
rng = random.Random(20260925)
latest = [0] * n_nodes
lines = []
wall = 1700000000000
for i in range(n_events):
    node = rng.randrange(n_nodes)
    latest[node] += 1
    comps = {node: latest[node]}
    for _ in range(3):
        other = rng.randrange(n_nodes)
        if latest[other]:
            comps[other] = latest[other]
    body = ",".join("n%04d:%d" % (k, comps[k]) for k in sorted(comps))
    lines.append("e%07d n%04d %d %s" % (i, node, wall + i * 7, body))
    wall += rng.randint(0, 3)
with open(out, "w") as fh:
    fh.write("\n".join(lines) + "\n")
