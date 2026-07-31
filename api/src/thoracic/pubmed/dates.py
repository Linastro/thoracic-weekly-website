"""Beijing 时区日期换算:previous_beijing_day 与 epdat_clause。"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
def previous_beijing_day(now: datetime | None = None) -> date:
    if now is None: now = datetime.now(BEIJING_TZ)
    else: now = now.astimezone(BEIJING_TZ)
    return (now - timedelta(days=1)).date()
def epdat_clause(target: date) -> str:
    s = target.isoformat(); return f"{s}:{s}[epdat]"
