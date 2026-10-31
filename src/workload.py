"""Synthetic zone + Zipf query generator."""
import random


def build_zone(n_domains, default_ttl=300):
    zone = {}
    for i in range(1, n_domains + 1):
        octet = (i % 254) + 1
        if i % 3 == 0:
            ip = f"192.0.2.{octet}"
        elif i % 3 == 1:
            ip = f"198.51.100.{octet}"
        else:
            ip = f"203.0.113.{octet}"
        zone[f"domain_{i:04d}.test"] = {"answer": ip, "ttl": default_ttl}
    return zone


def generate_zipf_queries(n_queries, n_domains, alpha, seed=42):
    rng = random.Random(seed)
    ranks = list(range(1, n_domains + 1))
    weights = [1.0 / (r ** alpha) for r in ranks]
    total = sum(weights)
    probs = [w / total for w in weights]
    indices = rng.choices(ranks, weights=probs, k=n_queries)
    return [f"domain_{i:04d}.test" for i in indices]