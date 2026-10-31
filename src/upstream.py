"""Simulated authoritative DNS server."""
import socket
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor
import protocol


class UpstreamServer(threading.Thread):
    def __init__(self, port, zone, delay_ms=50, jitter_ms=20,
                 seed=42, workers=100):
        super().__init__(daemon=True)
        self.port = port
        self.zone = zone
        self.delay = delay_ms / 1000.0
        self.jitter = jitter_ms / 1000.0
        self.rng = random.Random(seed)
        self.workers = workers
        self.running = True
        self.up = True
        self.query_count = 0
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
        if not self.up:
            return
        try:
            q = protocol.decode_query(data)
        except Exception:
            return
        with self._lock:
            self.query_count += 1
        time.sleep(self.delay + self.rng.uniform(0, self.jitter))
        qname = q["qname"]
        if qname in self.zone:
            r = self.zone[qname]
            resp = protocol.encode_response(q["txid"], qname, r["answer"], r["ttl"], 0)
        else:
            resp = protocol.encode_response(q["txid"], qname, None, 0, 3)
        try:
            self.sock.sendto(resp, addr)
        except Exception:
            pass

    def stop(self):
        self.running = False