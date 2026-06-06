from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

class FiringBase(BaseModel):
    kiln_number: str = Field(..., max_length=20)
    plan_temp_time: datetime
    status: str = Field(default='loading', pattern='^(loading|firing|cooling|completed)$')
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class FiringCreate(FiringBase):
    pass

class FiringUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern='^(loading|firing|cooling|completed)$')
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class FiringResponse(FiringBase):
    id: int
    created_at: datetime
    has_open_orders: bool = False

    model_config = ConfigDict(from_attributes=True)

class TemperatureReadingBase(BaseModel):
    firing_id: int
    segment: int = Field(..., ge=1, le=5)
    temperature: Decimal = Field(..., ge=-999.99, le=999.99)
    negative_pressure: Decimal = Field(..., ge=-999.99, le=999.99)
    recorded_at: Optional[datetime] = None

class TemperatureReadingCreate(TemperatureReadingBase):
    pass

class TemperatureReadingResponse(TemperatureReadingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class BrickBatchBase(BaseModel):
    firing_id: int
    batch_code: str = Field(..., max_length=50)
    color_grade: int = Field(..., ge=1, le=5)
    warpage_mm: Decimal = Field(..., ge=0, le=999.99)
    status: str = Field(default='produced', pattern='^(produced|rework_pending|rework_done|loaded|shipped)$')

class BrickBatchCreate(BrickBatchBase):
    pass

class BrickBatchUpdate(BaseModel):
    color_grade: Optional[int] = Field(None, ge=1, le=5)
    warpage_mm: Optional[Decimal] = Field(None, ge=0, le=999.99)
    status: Optional[str] = Field(None, pattern='^(produced|rework_pending|rework_done|loaded|shipped)$')

class BrickBatchResponse(BrickBatchBase):
    id: int
    created_at: datetime
    can_load: bool = True

    model_config = ConfigDict(from_attributes=True)

class WorkOrderBase(BaseModel):
    firing_id: int
    batch_id: Optional[int] = None
    order_type: str = Field(..., pattern='^(flue_collapse|rework)$')
    description: str
    status: str = Field(default='open', pattern='^(open|in_progress|closed)$')
    segment: Optional[int] = Field(None, ge=1, le=5)

class WorkOrderCreate(WorkOrderBase):
    pass

class WorkOrderUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern='^(open|in_progress|closed)$')
    closed_by: Optional[str] = None

class WorkOrderResponse(WorkOrderBase):
    id: int
    detected_at: datetime
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LoadingRecordBase(BaseModel):
    batch_id: int
    vehicle_plate: str = Field(..., max_length=20)
    operator: str = Field(..., max_length=100)
    quantity: int = Field(default=1, ge=1)
    remarks: Optional[str] = None

class LoadingRecordCreate(LoadingRecordBase):
    pass

class LoadingRecordResponse(LoadingRecordBase):
    id: int
    loading_time: datetime

    model_config = ConfigDict(from_attributes=True)

class FlueCollapseEventResponse(BaseModel):
    id: int
    firing_id: int
    segment: int
    start_time: datetime
    end_time: Optional[datetime] = None
    avg_temp_drop: Decimal
    duration_minutes: int
    work_order_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SegmentData(BaseModel):
    segment: int
    temperatures: List[Decimal]
    pressures: List[Decimal]
    timestamps: List[datetime]

class FiringDetailResponse(FiringResponse):
    segments: List[SegmentData]
    batches: List[BrickBatchResponse]
    orders: List[WorkOrderResponse]
    flue_events: List[FlueCollapseEventResponse]

    model_config = ConfigDict(from_attributes=True)
