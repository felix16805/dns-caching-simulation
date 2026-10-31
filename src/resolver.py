"""Caching resolver."""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import protocol


class ResolverServer(threading.Thread):
    def __init__(self, port, upstream_addr, cache,
                 workers=100, timeout_s=2.0):
        super().__init__(daemon=True)
        self.port = port
        self.upstream_addr = upstream_addr
        self.cache = cache
        self.workers = workers
        self.timeout_s = timeout_s
        self.running = True
        self.upstream_queries = 0
        self._lock = threading.Lock()
        self.ready = threading.Event()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", self.port))
        sock.settimeout(0.1)
        self.sock = sock
        self.executor = ThreadPoolExecutor(max_workers=self.workers)
        self.ready.set()
        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            self.executor.submit(self._handle, data, addr)
        self.executor.shutdown(wait=True)
        sock.close()

    def _handle(self, data, addr):
        try:
            q = protocol.decode_query(data)
        except Exception:
            return
        qname = q["qname"]
        now = time.time()

        answer, status, ttl = self.cache.lookup(qname, now)

        if status == "hit":
            self.sock.sendto(protocol.encode_response(
                q["txid"], qname, answer, ttl, 0), addr)
            return

        if status == "stale_hit":
            self.sock.sendto(protocol.encode_response(
                q["txid"], qname, answer, 30, 0), addr)
            return

        # ---- miss: go upstream ----
        with self._lock:
            self.upstream_queries += 1
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.settimeout(self.timeout_s)
        try:
            up.sendto(protocol.encode_query(q["txid"], qname), self.upstream_addr)
            raw, _ = up.recvfrom(4096)
            resp = protocol.decode_response(raw)
        except socket.timeout:
            e = self.cache.entries.get(qname)
            if e is not None and now < e.expires_at + 3600:
                self.cache.stats["stale_serves"] += 1
                self.sock.sendto(protocol.encode_response(
                    q["txid"], qname, e.answer, 30, 0), addr)
            else:
                self.sock.sendto(protocol.encode_response(
                    q["txid"], qname, None, 0, 2), addr)
            return
        finally:
            up.close()

        now = time.time()
        if resp["answer"] is not None:
            self.cache.insert(qname, resp["answer"], resp["ttl"], now, is_negative=False)
        elif resp["rcode"] == 3:
            self.cache.insert(qname, None, resp["ttl"] or 60, now, is_negative=True)

        self.sock.sendto(protocol.encode_response(
            q["txid"], qname, resp["answer"], resp["ttl"], resp["rcode"]
        ), addr)

    def stop(self):
        self.running = False