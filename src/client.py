"""Client + concurrent workload runner."""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import protocol


class Client:
    def __init__(self, resolver_addr, timeout_s=3.0):
        self.resolver_addr = resolver_addr
        self.timeout_s = timeout_s

    def query(self, qname, txid=0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_s)
        try:
            t0 = time.time()
            sock.sendto(protocol.encode_query(txid, qname), self.resolver_addr)
            raw, _ = sock.recvfrom(4096)
            ms = (time.time() - t0) * 1000
            r = protocol.decode_response(raw)
            return {"qname": qname, "latency_ms": ms,
                    "status": "ok" if r["rcode"] == 0 else "error",
                    "rcode": r["rcode"]}
        except socket.timeout:
            return {"qname": qname, "latency_ms": self.timeout_s * 1000,
                    "status": "timeout", "rcode": -1}
        finally:
            sock.close()


def run_workload(resolver_addr, queries, concurrency=5, timeout_s=3.0):
    results, lock = [], threading.Lock()

    def worker(chunk):
        c = Client(resolver_addr, timeout_s)
        local = [c.query(q) for q in chunk]
        with lock:
            results.extend(local)

    n = len(queries)
    size = max(1, n // concurrency)
    chunks = [queries[i:i + size] for i in range(0, n, size)]
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for f in [ex.submit(worker, ch) for ch in chunks]:
            f.result()
    return results