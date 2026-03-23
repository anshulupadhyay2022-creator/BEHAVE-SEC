import hashlib
import json
from typing import List, Any
from collections import deque

class ReplayDefender:
    """
    In-memory security mechanism to prevent Behavioral Biometric Replay Attacks.
    Maintains a rolling cache of recent behavioral payload hashes.
    """
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache_set = set()
        self._cache_queue = deque()

    def _hash_events(self, events: List[Any]) -> str:
        # Create a deterministic string from the exact timing sequences of events
        # It is statistically impossible for a human to recreate the exact millisecond sequence twice
        event_str = json.dumps([
            {
                "t": getattr(e, 'timestamp', 0), 
                "r": getattr(e, 'relativeTime', 0), 
                "ty": getattr(e, 'eventType', '')
            } 
            for e in events
        ], sort_keys=True)
        return hashlib.sha256(event_str.encode("utf-8")).hexdigest()

    def is_replay(self, events: List[Any]) -> bool:
        if not events or len(events) < 5:
            # Too short to reliably hash/fingerprint without false positives
            return False
            
        events_hash = self._hash_events(events)
        
        if events_hash in self._cache_set:
            return True
            
        # Add to cache
        self._cache_set.add(events_hash)
        self._cache_queue.append(events_hash)
        
        # Enforce max size
        if len(self._cache_queue) > self.max_size:
            oldest = self._cache_queue.popleft()
            self._cache_set.discard(oldest)
            
        return False

# Global Singleton Instance
replay_defender = ReplayDefender()
