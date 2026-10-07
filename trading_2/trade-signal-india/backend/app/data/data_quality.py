from datetime import datetime, timezone
from typing import NamedTuple, Optional, List


class DataQualityResult(NamedTuple):
    is_healthy: bool
    status: str
    latency_ms: float
    details: str


class DataQualityEngine:
    """Validates incoming live/tick data freshness, latency (<300ms target), sequencing, and timestamps."""

    def __init__(self, max_allowed_staleness_seconds: int = 10, max_latency_threshold_ms: float = 300.0):
        self.max_staleness = max_allowed_staleness_seconds
        self.max_latency_threshold_ms = max_latency_threshold_ms
        self.last_seen_timestamp: Optional[datetime] = None

    def check_freshness(self, last_tick_timestamp: datetime) -> DataQualityResult:
        now = datetime.now(timezone.utc)
        if last_tick_timestamp.tzinfo is None:
            last_tick_timestamp = last_tick_timestamp.replace(tzinfo=timezone.utc)
        
        diff_seconds = (now - last_tick_timestamp).total_seconds()
        latency_ms = max(0.0, diff_seconds * 1000.0)

        # Reject future timestamps (clock desync > 2 seconds)
        if diff_seconds < -2.0:
            return DataQualityResult(
                is_healthy=False,
                status="DATA_FUTURE_TIMESTAMP",
                latency_ms=latency_ms,
                details=f"Tick timestamp is in the future by {-diff_seconds:.2f}s (Clock desync detected)"
            )

        # Reject stale data
        if diff_seconds > self.max_staleness:
            return DataQualityResult(
                is_healthy=False,
                status="DATA_STALE",
                latency_ms=latency_ms,
                details=f"Tick is {diff_seconds:.1f}s old (exceeds {self.max_staleness}s threshold)"
            )

        # Sequence monotonic check
        if self.last_seen_timestamp is not None and last_tick_timestamp < self.last_seen_timestamp:
            return DataQualityResult(
                is_healthy=False,
                status="OUT_OF_ORDER_TICK",
                latency_ms=latency_ms,
                details=f"Tick timestamp {last_tick_timestamp} arrived out-of-order behind last seen {self.last_seen_timestamp}"
            )

        self.last_seen_timestamp = last_tick_timestamp

        # Microstructure latency audit warning
        if latency_ms > self.max_latency_threshold_ms:
            status = "HIGH_LATENCY_WARNING"
            details = f"Data feed fresh but latency {latency_ms:.1f}ms exceeds target threshold {self.max_latency_threshold_ms}ms"
        else:
            status = "HEALTHY"
            details = "Data feed verified, fresh, and low latency"

        return DataQualityResult(
            is_healthy=True,
            status=status,
            latency_ms=latency_ms,
            details=details
        )
