"""Generate plots and summary from sweep.csv (searches multiple locations)."""
import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path=None):
    candidates = [
        path,
        "results/sweep.csv",
        "src/results/sweep.csv",
        os.path.join(os.path.dirname(__file__), "..", "src", "results", "sweep.csv"),
        os.path.join(os.path.dirname(__file__), "..", "results", "sweep.csv"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            with open(p) as f:
                return list(csv.DictReader(f))
    raise FileNotFoundError(
        "sweep.csv not found. Run 'python src/run_experiment.py --mode sweep' first."
    )


def plot_hit_vs_ttl(rows, out="results/hit_vs_ttl.png"):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for p in ["lru", "lfu", "hybrid"]:
        s = [r for r in rows if r["policy"] == p
             and float(r["max_size"]) == 500 and float(r["alpha"]) == 1.0]
        s.sort(key=lambda r: float(r["ttl"]))
        ax.plot([float(r["ttl"]) for r in s],
                [float(r["hit_rate"]) for r in s], marker="o", label=p)
    ax.set_xscale("log")
    ax.set_xlabel("TTL (s)")
    ax.set_ylabel("Hit rate")
    ax.set_title("Hit rate vs TTL (size=500, alpha=1.0)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print("Wrote", out)


def plot_latency_bars(rows, out="results/latency_bars.png"):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    policies = ["none", "lru", "lfu", "hybrid"]
    means, p50s, p95s = [], [], []
    for p in policies:
        s = [r for r in rows if r["policy"] == p
             and float(r["max_size"]) == 500
             and float(r["alpha"]) == 1.0
             and float(r["ttl"]) == 60]          # FIXED: 300 -> 60
        means.append(float(s[0]["mean_latency_ms"]) if s else 0)
        p50s.append(float(s[0]["p50_latency_ms"]) if s else 0)
        p95s.append(float(s[0]["p95_latency_ms"]) if s else 0)
    x = range(len(policies))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - 0.27 for i in x], means, 0.27, label="mean")
    ax.bar([i         for i in x], p50s,  0.27, label="p50")
    ax.bar([i + 0.27 for i in x], p95s,  0.27, label="p95")
    ax.set_xticks(list(x))
    ax.set_xticklabels(policies)
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency by policy (size=500, alpha=1.0, TTL=60)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print("Wrote", out)


def plot_upstream_vs_ttl(rows, out="results/upstream_vs_ttl.png"):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for p in ["none", "lru", "lfu", "hybrid"]:
        s = [r for r in rows if r["policy"] == p
             and float(r["max_size"]) == 500 and float(r["alpha"]) == 1.0]
        s.sort(key=lambda r: float(r["ttl"]))
        ax.plot([float(r["ttl"]) for r in s],
                [float(r["upstream_queries"]) for r in s], marker="o", label=p)
    ax.set_xscale("log")
    ax.set_xlabel("TTL (s)")
    ax.set_ylabel("Upstream queries")
    ax.set_title("Upstream load vs TTL (size=500, alpha=1.0)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out)
    plt.close()
    print("Wrote", out)


def summary_table(rows, out="results/summary.md"):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    best = {}
    for r in rows:
        p = r["policy"]
        if p not in best or float(r["hit_rate"]) > float(best[p]["hit_rate"]):
            best[p] = r
    with open(out, "w") as f:
        f.write("| Policy | Best hit rate | TTL | Size | Alpha | p95 (ms) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for p, r in best.items():
            f.write(f"| {p} | {float(r['hit_rate']):.2%} | {r['ttl']} | "
                    f"{r['max_size']} | {r['alpha']} | "
                    f"{float(r['p95_latency_ms']):.1f} |\n")
    print("Wrote", out)


if __name__ == "__main__":
    rows = load()
    plot_hit_vs_ttl(rows)
    plot_latency_bars(rows)
    plot_upstream_vs_ttl(rows)
    summary_table(rows)