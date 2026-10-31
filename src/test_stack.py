"""End-to-end sanity test for the whole stack. Run this first."""
import socket
import time
import protocol
from cache import Cache, HybridPolicy
from workload import build_zone
from upstream import UpstreamServer
from resolver import ResolverServer


def test_cache():
    print("[1/4] Testing cache module...")
    c = Cache(HybridPolicy(), max_size=2)
    now = time.time()
    assert c.lookup("a.test", now) == (None, "miss", 0)
    c.insert("a.test", "1.2.3.4", 10, now)
    ans, status, ttl = c.lookup("a.test", now + 1)
    assert status == "hit" and ans == "1.2.3.4"
    ans, status, ttl = c.lookup("a.test", now + 11)
    assert status == "stale_hit"
    ans, status, ttl = c.lookup("a.test", now + 50)
    assert status == "expired"
    print("     PASS")


def test_upstream():
    print("[2/4] Testing upstream server...")
    zone = build_zone(10)
    up = UpstreamServer(5400, zone, delay_ms=50)
    up.start()
    assert up.ready.wait(timeout=2)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    t0 = time.time()
    sock.sendto(protocol.encode_query(1, "domain_0001.test"), ("127.0.0.1", 5400))
    raw, _ = sock.recvfrom(4096)
    ms = (time.time() - t0) * 1000
    r = protocol.decode_response(raw)
    sock.close()
    up.stop()
    up.join(timeout=5)
    assert r["rcode"] == 0
    assert 40 < ms < 100, f"unexpected latency {ms} ms"
    print(f"     PASS (latency {ms:.1f} ms)")


def test_resolver():
    print("[3/4] Testing resolver (miss vs hit)...")
    zone = build_zone(10)
    up = UpstreamServer(5400, zone, delay_ms=50)
    up.start()
    up.ready.wait(timeout=2)

    cache = Cache(HybridPolicy(), max_size=100)
    res = ResolverServer(5300, ("127.0.0.1", 5400), cache)
    res.start()
    res.ready.wait(timeout=2)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    def q(txid, name):
        t0 = time.time()
        sock.sendto(protocol.encode_query(txid, name), ("127.0.0.1", 5300))
        raw, _ = sock.recvfrom(4096)
        return protocol.decode_response(raw), (time.time() - t0) * 1000

    r1, t1 = q(1, "domain_0001.test")
    r2, t2 = q(2, "domain_0001.test")
    sock.close()
    res.stop()
    up.stop()
    res.join(timeout=5)
    up.join(timeout=5)

    assert t1 > 40, f"miss should be slow, got {t1:.1f} ms"
    assert t2 < 10, f"hit should be fast, got {t2:.1f} ms"
    print(f"     PASS (miss {t1:.1f} ms, hit {t2:.1f} ms)")


def test_demo():
    print("[4/4] Running full demo...")
    from run_experiment import run_one
    m = run_one("hybrid", 500, 300, 200, 100, 1.0,
                concurrency=5, upstream_delay_ms=50)
    assert 0.5 < m["hit_rate"] < 1.0, f"unexpected hit rate {m['hit_rate']}"
    assert m["p95_latency_ms"] > 30, "p95 should reflect some misses"
    print(f"     PASS (hit rate {m['hit_rate']:.1%}, p95 {m['p95_latency_ms']:.1f} ms)")


if __name__ == "__main__":
    test_cache()
    test_upstream()
    test_resolver()
    test_demo()
    print("\nAll tests passed.")