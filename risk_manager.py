from datetime import datetime, timezone
from typing import Optional, Tuple


class DailyRiskManager:
    """Tracks daily PnL vs starting equity (UTC day) and signals stop conditions."""

    def __init__(self, target_roi: float, loss_limit_roi: float):
        self.target = target_roi
        self.loss_limit = loss_limit_roi
        self._day: Optional[object] = None
        self._day_start_equity: Optional[float] = None

    def update(self, equity: float) -> None:
        today = datetime.now(timezone.utc).date()
        if self._day != today:
            self._day = today
            self._day_start_equity = equity

    def roi(self, equity: float) -> float:
        if not self._day_start_equity:
            return 0.0
        return (equity - self._day_start_equity) / self._day_start_equity

    def should_stop(self, equity: float) -> Tuple[bool, str]:
        r = self.roi(equity)
        if r >= self.target:
            return True, f"daily target reached: {r*100:.2f}%"
        if r <= self.loss_limit:
            return True, f"daily loss limit hit: {r*100:.2f}%"
        return False, ""
