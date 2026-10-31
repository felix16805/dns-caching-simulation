"""Orchestrator: sweep, outage, demo.
Results are always written to <project_root>/results/, regardless of CWD."""
import argparse
import csv
import os
import time

from cache import Cache, LRUPolicy, LFUPolicy, HybridPolicy
from workload import build_zone, generate_zipf_queries
from upstream import UpstreamServer
from resolver import ResolverServer
from client import run_workload


POLICY_MAP = {
    "lru": LRUPolicy(),
    "lfu": LFUPolicy(),
    "hybrid": HybridPolicy(),
}


def get_results_dir():
    """Return <project_root>/results, creating it if needed."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_dir = os.path.join(project_root, "results")
    os.makedirs(results_dir, exist_ok=True)
    return results_dir


def compute_metrics(results, cache, upstream):
    lat = sorted(r["latency_ms"] for r in results)
    n = len(lat)
    if n == 0:
        return {}
    hits, misses = cache.stats["hits"], cache.stats["misses"]
    return {
        "n_queries": n,
        "hit_rate": hits / max(1, hits + misses),
        "hits": hits,
        "misses": misses,
        "stale_serves": cache.stats["stale_serves"],
        "evictions": cache.stats["evictions"],
        "inserts": cache.stats["inserts"],
        "cache_size": cache.size(),
        "upstream_queries": upstream.query_count,
        "mean_latency_ms": sum(lat) / n,
        "p50_latency_ms": lat[int(0.50 * (n - 1))],
        "p95_latency_ms": lat[int(0.95 * (n - 1))],
        "p99_latency_ms": lat[int(0.99 * (n - 1))],
        "timeouts": sum(1 for r in results if r["status"] == "timeout"),
        "errors": sum(1 for r in results if r["status"] == "error"),
    }


def run_one(policy_name, max_size, ttl, n_queries, n_domains, alpha,
            concurrency=5, upstream_delay_ms=10):
    """Run one configuration. Returns a dict of metrics."""
    if policy_name == "none":
        cache = Cache(LRUPolicy(), max_size=0)
    else:
        cache = Cache(POLICY_MAP[policy_name], max_size=max_size,
                      max_ttl=ttl, neg_ttl_ratio=0.25, stale_grace=30.0)

    zone = build_zone(n_domains, default_ttl=ttl)
    queries = generate_zipf_queries(n_queries, n_domains, alpha)

    up = UpstreamServer(5400, zone, delay_ms=upstream_delay_ms,
                        jitter_ms=5, workers=100)
    up.start()
    if not up.ready.wait(timeout=2):
        raise RuntimeError("Upstream server failed to start")

    res = ResolverServer(5300, ("127.0.0.1", 5400), cache, workers=100)
    res.start()
    if not res.ready.wait(timeout=2):
        raise RuntimeError("Resolver failed to start")

    try:
        results = run_workload(("127.0.0.1", 5300), queries,
                               concurrency=concurrency)
    finally:
        res.stop()
        up.stop()
        res.join(timeout=5)
        up.join(timeout=5)
        time.sleep(0.1)

    m = compute_metrics(results, cache, up)
    m.update(policy=policy_name, max_size=max_size, ttl=ttl, alpha=alpha,
             concurrency=concurrency)
    return m


def outage_test(policy_name="hybrid", max_size=500, ttl=5,
                n_warm=500, n_during=300, n_after=300, outage_s=10):
    """Test serve-stale behaviour during a simulated upstream outage."""
    cache = Cache(POLICY_MAP[policy_name], max_size=max_size,
                  max_ttl=ttl, stale_grace=60.0)
    zone = build_zone(1000, default_ttl=ttl)
    queries = generate_zipf_queries(n_warm + n_during + n_after,
                                    1000, 1.0, seed=1)

    up = UpstreamServer(5400, zone, delay_ms=10, jitter_ms=2, workers=100)
    up.start()
    up.ready.wait(timeout=2)

    res = ResolverServer(5300, ("127.0.0.1", 5400), cache,
                         workers=100, timeout_s=1.5)
    res.start()
    res.ready.wait(timeout=2)

    try:
        # Warm cache
        run_workload(("127.0.0.1", 5300), queries[:n_warm], concurrency=5)
        # Wait for entries to expire (TTL=5)
        time.sleep(ttl + 1)
        # Trigger outage
        up.up = False
        t0 = time.time()
        during = run_workload(("127.0.0.1", 5300),
                              queries[n_warm:n_warm + n_during],
                              concurrency=5)
        elapsed = time.time() - t0
        if elapsed < outage_s:
            time.sleep(outage_s - elapsed)
        up.up = True
        after = run_workload(("127.0.0.1", 5300),
                             queries[n_warm + n_during:],
                             concurrency=5)
    finally:
        res.stop()
        up.stop()
        res.join(timeout=5)
        up.join(timeout=5)
        time.sleep(0.1)

    return {
        "during_success_rate": sum(1 for r in during if r["status"] == "ok") / max(1, len(during)),
        "during_mean_latency_ms": sum(r["latency_ms"] for r in during) / max(1, len(during)),
        "after_success_rate": sum(1 for r in after if r["status"] == "ok") / max(1, len(after)),
        "stale_serves": cache.stats["stale_serves"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["sweep", "outage", "demo"], default="sweep")
    args = p.parse_args()

    results_dir = get_results_dir()
    print(f"Results directory: {results_dir}")

    if args.mode == "demo":
        m = run_one("hybrid", 500, 300, 200, 100, 1.0,
                    concurrency=5, upstream_delay_ms=50)
        for k, v in m.items():
            print(f"  {k}: {v}")
        return

    if args.mode == "outage":
        m = outage_test()
        print("Outage test results:")
        for k, v in m.items():
            print(f"  {k}: {v}")
        out_path = os.path.join(results_dir, "outage.csv")
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(m.keys()))
            w.writeheader()
            w.writerow(m)
        print(f"\nWrote {out_path}")
        return

    # ---- sweep ----
    # NOTE: if hit rates are flat across TTLs because the run is shorter than
    # every TTL, reduce to [2, 10, 60, 300].
    configs = []
    for policy in ["none", "lru", "lfu", "hybrid"]:
        for size in [50, 500, 5000]:
            for ttl in [10, 60, 600, 3600]:
                for alpha in [0.8, 1.0, 1.2]:
                    configs.append((policy, size, ttl, 2000, 1000, alpha, 5, 10))

    rows = []
    for i, cfg in enumerate(configs):
        m = run_one(*cfg)
        rows.append(m)
        print(f"[{i+1}/{len(configs)}] {cfg}  hit={m['hit_rate']:.1%}  "
              f"p95={m['p95_latency_ms']:.1f}ms  up={m['upstream_queries']}")

    out_path = os.path.join(results_dir, "sweep.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()