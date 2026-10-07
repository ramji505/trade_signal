import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from app.core.config import settings


@dataclass
class EventRiskStatus:
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"]
    event_name: Optional[str]
    allow_trading: bool
    confidence_penalty: int


class EventRiskFilter:
    """Schedule-based veto for high-impact macro/news events."""

    def __init__(self, events_json: Optional[str] = None, window_minutes: Optional[int] = None):
        raw = events_json if events_json is not None else settings.HIGH_RISK_EVENTS_JSON
        try:
            payload = json.loads(raw or "[]")
            self.high_risk_events = payload if isinstance(payload, list) else []
        except json.JSONDecodeError:
            self.high_risk_events = []
        self.window_minutes = window_minutes if window_minutes is not None else settings.EVENT_RISK_WINDOW_MINUTES

    def evaluate_risk(self, current_dt: Optional[datetime] = None) -> EventRiskStatus:
        current_dt = current_dt or datetime.now(timezone.utc)
        if current_dt.tzinfo is None:
            current_dt = current_dt.replace(tzinfo=timezone.utc)
        for event in self.high_risk_events:
            if not isinstance(event, dict) or not event.get("timestamp"):
                continue
            try:
                event_dt = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=current_dt.tzinfo)
            except ValueError:
                continue
            minutes = abs((current_dt - event_dt).total_seconds()) / 60.0
            if minutes <= self.window_minutes:
                level = str(event.get("risk_level", "HIGH")).upper()
                if level not in {"HIGH", "EXTREME"}:
                    level = "HIGH"
                penalty = 25 if level == "HIGH" else 40
                return EventRiskStatus(level, str(event.get("name", "Scheduled high-risk event")), False, penalty)
        return EventRiskStatus("LOW", None, True, 0)
