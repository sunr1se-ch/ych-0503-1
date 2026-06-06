from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import time

from database import get_db, settings, engine
from models import Base
from crud import (
    get_firings, get_firing, create_firing, update_firing,
    create_temperature_reading, get_temperature_readings,
    get_batches, get_batch, create_brick_batch, update_brick_batch,
    get_work_orders, get_work_order, create_work_order, update_work_order,
    create_loading_record, get_loading_records,
    get_flue_collapse_events, scan_flue_collapse, has_open_orders
)
from schemas import (
    FiringCreate, FiringUpdate, FiringResponse,
    TemperatureReadingCreate, TemperatureReadingResponse,
    BrickBatchCreate, BrickBatchUpdate, BrickBatchResponse,
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse,
    LoadingRecordCreate, LoadingRecordResponse,
    FiringDetailResponse, SegmentData, FlueCollapseEventResponse
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_retries = 10
retry_count = 0
while retry_count < max_retries:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        break
    except Exception as e:
        retry_count += 1
        logger.warning(f"Database connection failed (attempt {retry_count}/{max_retries}): {e}")
        if retry_count >= max_retries:
            logger.error("Failed to connect to database after maximum retries")
            raise
        time.sleep(5)

app = FastAPI(title="砖窑作坊温度监控系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()

def scheduled_scan():
    try:
        db = next(get_db())
        events = scan_flue_collapse(db)
        if events:
            logger.info(f"扫描发现 {len(events)} 个烟道塌陷事件")
            for event in events:
                logger.info(f"  窑道{event['kiln_number']} 段{event['segment']}: 降温{event['avg_temp_drop']:.1f}°C, 持续{event['duration_minutes']:.0f}分钟")
    except Exception as e:
        logger.error(f"定时扫描错误: {e}")
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(
        scheduled_scan,
        IntervalTrigger(minutes=settings.SCAN_INTERVAL_MINUTES),
        id="flue_collapse_scan",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Scheduler started, scanning every {settings.SCAN_INTERVAL_MINUTES} minutes")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler stopped")

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {e}")

@app.get("/api/firings", response_model=List[FiringResponse])
def list_firings(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    return get_firings(db, skip=skip, limit=limit)

@app.get("/api/firings/{firing_id}", response_model=FiringDetailResponse)
def get_firing_detail(firing_id: int, db: Session = Depends(get_db)):
    firing = get_firing(db, firing_id)
    if not firing:
        raise HTTPException(status_code=404, detail="窑次不存在")
    
    readings = get_temperature_readings(db, firing_id)
    segments_data = []
    for seg in range(1, 6):
        seg_readings = [r for r in readings if r.segment == seg]
        segments_data.append(SegmentData(
            segment=seg,
            temperatures=[r.temperature for r in seg_readings],
            pressures=[r.negative_pressure for r in seg_readings],
            timestamps=[r.recorded_at for r in seg_readings]
        ))
    
    batches = get_batches(db, firing_id=firing_id)
    orders = get_work_orders(db)
    orders = [o for o in orders if o.firing_id == firing_id]
    flue_events = get_flue_collapse_events(db, firing_id=firing_id)
    
    return FiringDetailResponse(
        id=firing.id,
        kiln_number=firing.kiln_number,
        plan_temp_time=firing.plan_temp_time,
        status=firing.status,
        start_time=firing.start_time,
        end_time=firing.end_time,
        created_at=firing.created_at,
        has_open_orders=has_open_orders(db, firing_id),
        segments=segments_data,
        batches=batches,
        orders=orders,
        flue_events=flue_events
    )

@app.post("/api/firings", response_model=FiringResponse, status_code=201)
def add_firing(firing: FiringCreate, db: Session = Depends(get_db)):
    return create_firing(db, firing)

@app.put("/api/firings/{firing_id}", response_model=FiringResponse)
def modify_firing(firing_id: int, firing: FiringUpdate, db: Session = Depends(get_db)):
    updated = update_firing(db, firing_id, firing)
    if not updated:
        raise HTTPException(status_code=404, detail="窑次不存在")
    return updated

@app.post("/api/readings", response_model=TemperatureReadingResponse, status_code=201)
def add_reading(reading: TemperatureReadingCreate, db: Session = Depends(get_db)):
    firing = get_firing(db, reading.firing_id)
    if not firing:
        raise HTTPException(status_code=404, detail="窑次不存在")
    return create_temperature_reading(db, reading)

@app.get("/api/firings/{firing_id}/readings", response_model=List[TemperatureReadingResponse])
def list_readings(
    firing_id: int, 
    segment: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db)
):
    firing = get_firing(db, firing_id)
    if not firing:
        raise HTTPException(status_code=404, detail="窑次不存在")
    return get_temperature_readings(db, firing_id, segment)

@app.get("/api/batches", response_model=List[BrickBatchResponse])
def list_batches(
    firing_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return get_batches(db, firing_id=firing_id, skip=skip, limit=limit)

@app.get("/api/batches/{batch_id}", response_model=BrickBatchResponse)
def get_batch_detail(batch_id: int, db: Session = Depends(get_db)):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    return batch

@app.post("/api/batches", response_model=BrickBatchResponse, status_code=201)
def add_batch(batch: BrickBatchCreate, db: Session = Depends(get_db)):
    firing = get_firing(db, batch.firing_id)
    if not firing:
        raise HTTPException(status_code=404, detail="窑次不存在")
    return create_brick_batch(db, batch)

@app.put("/api/batches/{batch_id}", response_model=BrickBatchResponse)
def modify_batch(batch_id: int, batch: BrickBatchUpdate, db: Session = Depends(get_db)):
    updated = update_brick_batch(db, batch_id, batch)
    if not updated:
        raise HTTPException(status_code=404, detail="批次不存在")
    return updated

@app.get("/api/orders", response_model=List[WorkOrderResponse])
def list_orders(
    status: Optional[str] = Query(None, pattern="^(open|in_progress|closed)$"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return get_work_orders(db, status=status, skip=skip, limit=limit)

@app.get("/api/orders/{order_id}", response_model=WorkOrderResponse)
def get_order_detail(order_id: int, db: Session = Depends(get_db)):
    order = get_work_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    return order

@app.post("/api/orders", response_model=WorkOrderResponse, status_code=201)
def add_order(order: WorkOrderCreate, db: Session = Depends(get_db)):
    firing = get_firing(db, order.firing_id)
    if not firing:
        raise HTTPException(status_code=404, detail="窑次不存在")
    return create_work_order(db, order)

@app.put("/api/orders/{order_id}", response_model=WorkOrderResponse)
def modify_order(order_id: int, order: WorkOrderUpdate, db: Session = Depends(get_db)):
    updated = update_work_order(db, order_id, order)
    if not updated:
        raise HTTPException(status_code=404, detail="工单不存在")
    return updated

@app.post("/api/loading", response_model=LoadingRecordResponse, status_code=201)
def add_loading(loading: LoadingRecordCreate, db: Session = Depends(get_db)):
    result, message = create_loading_record(db, loading)
    if not result:
        raise HTTPException(status_code=400, detail=message)
    return result

@app.get("/api/loading", response_model=List[LoadingRecordResponse])
def list_loading_records(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return get_loading_records(db, skip=skip, limit=limit)

@app.get("/api/flue-events", response_model=List[FlueCollapseEventResponse])
def list_flue_events(
    firing_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return get_flue_collapse_events(db, firing_id=firing_id)

@app.post("/api/scan-flue-collapse")
def manual_scan(db: Session = Depends(get_db)):
    events = scan_flue_collapse(db)
    return {"detected_events": len(events), "events": events}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
