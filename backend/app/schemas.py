import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_time(v: str) -> str:
    if not _HHMM.match(v):
        raise ValueError("Giờ phải có dạng HH:MM (00:00 - 23:59)")
    return v


class StationIn(BaseModel):
    id: Optional[str] = Field(None, max_length=20)
    name: str = Field(..., min_length=1, max_length=120)
    district: Optional[str] = Field("", max_length=80)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class StationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    district: Optional[str] = Field(None, max_length=80)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)


class RouteIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-]+$")
    name: str = Field(..., min_length=1, max_length=160)
    headway_min: int = Field(..., ge=1, le=240)
    first_departure: str
    last_departure: str
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    stops: list[str] = Field(..., min_length=2)

    _t1 = field_validator("first_departure", "last_departure")(_check_time)


class RouteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    headway_min: Optional[int] = Field(None, ge=1, le=240)
    first_departure: Optional[str] = None
    last_departure: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    stops: Optional[list[str]] = Field(None, min_length=2)

    @field_validator("first_departure", "last_departure")
    @classmethod
    def _t(cls, v):
        return _check_time(v) if v is not None else v


class DepartureIn(BaseModel):
    direction: str = Field("out", pattern=r"^(out|in)$")
    time: str

    _t = field_validator("time")(_check_time)


class SegmentIn(BaseModel):
    from_id: str
    to_id: str
    distance_km: float = Field(..., gt=0, le=100)
    time_min: float = Field(..., gt=0, le=300)
