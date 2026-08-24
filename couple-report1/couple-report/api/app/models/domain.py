"""DB 행을 표현할 도메인 dataclass의 최소 골격."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class Couple:
    id: str
    status: str


@dataclass(slots=True)
class Message:
    id: int
    couple_id: str
    sender: str
    sent_at: datetime


@dataclass(slots=True)
class Session:
    id: int
    couple_id: str
    started_at: datetime


@dataclass(slots=True)
class WeeklyMetric:
    couple_id: str
    week_start: date


@dataclass(slots=True)
class Report:
    couple_id: str
    week_start: date


@dataclass(slots=True)
class Note:
    id: int
    couple_id: str

