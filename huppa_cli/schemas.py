from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AliasPath, BaseModel, BeforeValidator, Field, field_serializer, field_validator, model_validator

AMS = ZoneInfo("Europe/Amsterdam")


def _parse_utc_to_ams(v: str | datetime) -> datetime:
    """Parse a UTC ISO timestamp and convert to Amsterdam local time."""
    if isinstance(v, str):
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.astimezone(AMS)
    return v


AmsDatetime = Annotated[datetime, BeforeValidator(_parse_utc_to_ams)]


class Occurrence(BaseModel):
    """Base schema for fields shared across occurrences and bookings."""

    id: str
    name: str
    category: str = Field(validation_alias=AliasPath("category", "name"))
    starts_at: AmsDatetime = Field(validation_alias="startsAt")
    ends_at: AmsDatetime = Field(validation_alias="endsAt")
    available_slots: int = Field(validation_alias="availableSlots")
    is_full: bool = Field(validation_alias="isFull")
    is_eligible_to_book: bool = Field(validation_alias="isEligibleToBook")
    trainers: list[str] = []

    @field_validator("trainers", mode="before")
    @classmethod
    def extract_trainer_names(cls, v: list) -> list[str]:
        if v and isinstance(v[0], dict):
            return [t["name"] for t in v]
        return v

    @field_serializer("starts_at", "ends_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M")


class AvailableClass(Occurrence):
    """An occurrence from the schedule/occurrences endpoint."""

    organization_id: str = Field(validation_alias=AliasPath("category", "organizationId"))
    is_booked: bool = False
    is_on_waitlist: bool = False

    @model_validator(mode="before")
    @classmethod
    def derive_is_booked(cls, data: dict) -> dict:
        user = data.get("occurrenceUser") or {}
        data["is_booked"] = user.get("status") == "confirmed"
        data["is_on_waitlist"] = data.get("occurrenceWaitlistId") is not None
        return data


class Booking(Occurrence):
    """An occurrence from the bookings-and-waitlists endpoint."""

    booking_status: str | None = None
    is_on_waitlist: bool = False

    @model_validator(mode="before")
    @classmethod
    def flatten_booking_and_waitlist(cls, data: dict) -> dict:
        booking = data.get("booking")
        if booking:
            data["booking_status"] = booking.get("status")
        waitlist = data.get("waitlist")
        if waitlist:
            data["is_on_waitlist"] = waitlist.get("isOnWaitlist", False)
        return data


class Membership(BaseModel):
    """A booking product / membership."""

    name: str
    status: str
    credits: int
    total_credits: int = Field(validation_alias="totalCredits")
    last_payment_date: AmsDatetime | None = Field(default=None, validation_alias="lastPaymentDate")
    next_payment_date: AmsDatetime | None = Field(default=None, validation_alias="nextPaymentDate")
    started_at: AmsDatetime | None = Field(default=None, validation_alias="startedAt")

    @field_serializer("last_payment_date", "next_payment_date", "started_at")
    def serialize_optional_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return dt.strftime("%Y-%m-%d %H:%M")
