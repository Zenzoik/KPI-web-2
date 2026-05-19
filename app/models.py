from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20), default="user")

    issue_records: Mapped[list["IssueRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FuelType(Base):
    __tablename__ = "fuel_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text(), default="")

    fuels: Mapped[list["FuelItem"]] = relationship(back_populates="fuel_type")


class FuelItem(Base):
    __tablename__ = "fuel_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    supplier: Mapped[str] = mapped_column(String(120))
    quantity_liters: Mapped[int] = mapped_column(Integer(), default=0)
    unit_price: Mapped[int] = mapped_column(Integer(), default=0)
    description: Mapped[str] = mapped_column(Text(), default="")
    fuel_type_id: Mapped[int] = mapped_column(ForeignKey("fuel_types.id"))

    fuel_type: Mapped["FuelType"] = relationship(back_populates="fuels")
    issue_records: Mapped[list["IssueRecord"]] = relationship(
        back_populates="fuel_item", cascade="all, delete-orphan"
    )


class IssueRecord(Base):
    __tablename__ = "issue_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    fuel_item_id: Mapped[int] = mapped_column(ForeignKey("fuel_items.id"))
    amount_liters: Mapped[int] = mapped_column(Integer(), default=0)
    destination: Mapped[str] = mapped_column(String(120))
    issued_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="issue_records")
    fuel_item: Mapped["FuelItem"] = relationship(back_populates="issue_records")
