"""Cache with LRU, LFU and Hybrid (recency+frequency) eviction."""
import math
import threading
from dataclasses import dataclass


@dataclass
class CacheEntry:
    domain: str
    answer: str
    ttl: int
    inserted_at: float
    expires_at: float
    last_access: float
    access_count: int
    is_negative: bool


class LRUPolicy:
    name = "lru"

    def select_victim(self, entries, now):
        return min(entries, key=lambda d: entries[d].last_access)


class LFUPolicy:
    name = "lfu"

    def select_victim(self, entries, now):
        return min(entries, key=lambda d: entries[d].access_count)


class HybridPolicy:
    """score = count * exp(-age / ttl); evict lowest score."""
    name = "hybrid"

    def select_victim(self, entries, now):
        def score(e):
            age = now - e.last_access
            return e.access_count * math.exp(-age / max(e.ttl, 1.0))
        return min(entries, key=lambda d: score(entries[d]))


class Cache:
    def __init__(self, policy, max_size,
                 max_ttl=86400, neg_ttl_ratio=0.25, stale_grace=30.0):
        self.policy = policy
        self.max_size = max_size
        self.max_ttl = max_ttl
        self.neg_ttl_ratio = neg_ttl_ratio
        self.stale_grace = stale_grace
        self.entries = {}
        self._lock = threading.Lock()
        self.stats = {
            "hits": 0, "misses": 0, "expired": 0, "evictions": 0,
            "stale_serves": 0, "inserts": 0, "negative_inserts": 0,
        }

    def lookup(self, domain, now):
        """Return (answer, status, remaining_ttl)."""
        with self._lock:
            if self.max_size == 0:
                self.stats["misses"] += 1
                return None, "disabled", 0
            entry = self.entries.get(domain)
            if entry is None:
                self.stats["misses"] += 1
                return None, "miss", 0
            if now < entry.expires_at:
                entry.last_access = now
                entry.access_count += 1
                self.stats["hits"] += 1
                return entry.answer, "hit", max(1, int(entry.expires_at - now))
            if self.stale_grace > 0 and now < entry.expires_at + self.stale_grace:
                self.stats["stale_serves"] += 1
                return entry.answer, "stale_hit", 30
            del self.entries[domain]
            self.stats["expired"] += 1
            self.stats["misses"] += 1
            return None, "expired", 0

    def insert(self, domain, answer, ttl, now, is_negative=False):
        with self._lock:
            if self.max_size == 0:
                return
            if is_negative:
                ttl = max(1, int(ttl * self.neg_ttl_ratio))
                self.stats["negative_inserts"] += 1
            ttl = min(ttl, self.max_ttl)
            if domain in self.entries:
                e = self.entries[domain]
                e.answer, e.ttl = answer, ttl
                e.expires_at = now + ttl
                e.last_access = now
                e.is_negative = is_negative
                return
            if len(self.entries) >= self.max_size:
                victim = self.policy.select_victim(self.entries, now)
                del self.entries[victim]
                self.stats["evictions"] += 1
            self.entries[domain] = CacheEntry(
                domain=domain, answer=answer, ttl=ttl,
                inserted_at=now, expires_at=now + ttl,
                last_access=now, access_count=1,
                is_negative=is_negative,
            )
            self.stats["inserts"] += 1

    def size(self):
        return len(self.entries)