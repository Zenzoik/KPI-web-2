from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FuelTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str


class FuelItemBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    supplier: str = Field(min_length=2, max_length=120)
    quantity_liters: int = Field(ge=0, le=999999)
    unit_price: int = Field(ge=0, le=100000)
    description: str = Field(default="", max_length=2000)
    fuel_type_id: int


class FuelItemCreate(FuelItemBase):
    pass


class FuelItemUpdate(FuelItemBase):
    pass


class FuelItemRead(FuelItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fuel_type: FuelTypeRead


class IssueCreate(BaseModel):
    amount_liters: int = Field(ge=1, le=999999)
    destination: str = Field(min_length=2, max_length=120)


class IssueRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_liters: int
    destination: str
    issued_at: datetime
    user_id: int
    fuel_item: FuelItemRead
