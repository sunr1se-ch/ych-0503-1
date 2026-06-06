from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from models import (
    Firing, TemperatureReading, BrickBatch, WorkOrder,
    LoadingRecord, FlueCollapseEvent
)
from schemas import (
    FiringCreate, FiringUpdate, TemperatureReadingCreate,
    BrickBatchCreate, BrickBatchUpdate, WorkOrderCreate,
    WorkOrderUpdate, LoadingRecordCreate
)

def get_firings(db: Session, skip: int = 0, limit: int = 100) -> List[Firing]:
    firings = db.query(Firing).order_by(Firing.created_at.desc()).offset(skip).limit(limit).all()
    for firing in firings:
        firing.has_open_orders = has_open_orders(db, firing.id)
    return firings

def get_firing(db: Session, firing_id: int) -> Optional[Firing]:
    firing = db.query(Firing).filter(Firing.id == firing_id).first()
    if firing:
        firing.has_open_orders = has_open_orders(db, firing_id)
    return firing

def create_firing(db: Session, firing: FiringCreate) -> Firing:
    db_firing = Firing(**firing.model_dump())
    db.add(db_firing)
    db.commit()
    db.refresh(db_firing)
    return db_firing

def update_firing(db: Session, firing_id: int, firing: FiringUpdate) -> Optional[Firing]:
    db_firing = get_firing(db, firing_id)
    if db_firing:
        update_data = firing.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_firing, key, value)
        db.commit()
        db.refresh(db_firing)
    return db_firing

def has_open_orders(db: Session, firing_id: int, lock: bool = False) -> bool:
    query = db.query(WorkOrder).filter(
        WorkOrder.firing_id == firing_id,
        WorkOrder.status != 'closed'
    )
    if lock:
        query = query.with_for_update()
    return query.first() is not None

def can_load_batch(db: Session, batch_id: int, lock: bool = False) -> Tuple[bool, str]:
    query = db.query(BrickBatch).filter(BrickBatch.id == batch_id)
    if lock:
        query = query.with_for_update()
    batch = query.first()
    if not batch:
        return False, "批次不存在"
    if batch.status in ('loaded', 'shipped'):
        return False, f"批次已{batch.status}"
    if batch.status == 'rework_pending':
        return False, "该批次待返工，禁止装车"
    if has_open_orders(db, batch.firing_id, lock=lock):
        return False, "该窑次存在未关闭工单，禁止装车"
    return True, "可以装车"

def create_temperature_reading(db: Session, reading: TemperatureReadingCreate) -> TemperatureReading:
    db_reading = TemperatureReading(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading

def get_temperature_readings(db: Session, firing_id: int, segment: Optional[int] = None) -> List[TemperatureReading]:
    query = db.query(TemperatureReading).filter(TemperatureReading.firing_id == firing_id)
    if segment:
        query = query.filter(TemperatureReading.segment == segment)
    return query.order_by(TemperatureReading.recorded_at.asc()).all()

def get_batches(db: Session, firing_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[BrickBatch]:
    query = db.query(BrickBatch).order_by(BrickBatch.created_at.desc())
    if firing_id:
        query = query.filter(BrickBatch.firing_id == firing_id)
    batches = query.offset(skip).limit(limit).all()
    for batch in batches:
        can_load, _ = can_load_batch(db, batch.id)
        batch.can_load = can_load
    return batches

def get_batch(db: Session, batch_id: int) -> Optional[BrickBatch]:
    batch = db.query(BrickBatch).filter(BrickBatch.id == batch_id).first()
    if batch:
        can_load, _ = can_load_batch(db, batch_id)
        batch.can_load = can_load
    return batch

def create_brick_batch(db: Session, batch: BrickBatchCreate) -> BrickBatch:
    db_batch = BrickBatch(**batch.model_dump())
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    check_and_create_rework_order(db, db_batch)
    return db_batch

def update_brick_batch(db: Session, batch_id: int, batch: BrickBatchUpdate) -> Optional[BrickBatch]:
    db_batch = get_batch(db, batch_id)
    if db_batch:
        update_data = batch.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_batch, key, value)
        db.commit()
        db.refresh(db_batch)
        check_and_create_rework_order(db, db_batch)
    return db_batch

def check_and_create_rework_order(db: Session, batch: BrickBatch) -> None:
    if batch.color_grade <= 2:
        has_flue_collapse = db.query(WorkOrder).filter(
            WorkOrder.firing_id == batch.firing_id,
            WorkOrder.order_type == 'flue_collapse',
            WorkOrder.status != 'closed'
        ).first() is not None
        
        if has_flue_collapse:
            existing_order = db.query(WorkOrder).filter(
                WorkOrder.batch_id == batch.id,
                WorkOrder.order_type == 'rework',
                WorkOrder.status != 'closed'
            ).first()
            
            if not existing_order:
                order = WorkOrder(
                    firing_id=batch.firing_id,
                    batch_id=batch.id,
                    order_type='rework',
                    description=f"批次{batch.batch_code}品级为{batch.color_grade}，需返工处理",
                    status='open'
                )
                db.add(order)
                batch.status = 'rework_pending'
                db.commit()

def get_work_orders(db: Session, status: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[WorkOrder]:
    query = db.query(WorkOrder).order_by(WorkOrder.detected_at.desc())
    if status:
        query = query.filter(WorkOrder.status == status)
    return query.offset(skip).limit(limit).all()

def get_work_order(db: Session, order_id: int) -> Optional[WorkOrder]:
    return db.query(WorkOrder).filter(WorkOrder.id == order_id).first()

def create_work_order(db: Session, order: WorkOrderCreate) -> WorkOrder:
    db_order = WorkOrder(**order.model_dump())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def update_work_order(db: Session, order_id: int, order: WorkOrderUpdate) -> Optional[WorkOrder]:
    try:
        db_order = db.query(WorkOrder).filter(WorkOrder.id == order_id).with_for_update().first()
        if not db_order:
            return None
        
        update_data = order.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_order, key, value)
        if order.status == 'closed':
            db_order.closed_at = datetime.utcnow()
        db.commit()
        db.refresh(db_order)
        
        if order.status == 'closed' and db_order.order_type == 'rework' and db_order.batch_id:
            batch = db.query(BrickBatch).filter(BrickBatch.id == db_order.batch_id).with_for_update().first()
            if batch and batch.status == 'rework_pending':
                batch.status = 'rework_done'
                db.commit()
        return db_order
    except Exception as e:
        db.rollback()
        raise e

def create_loading_record(db: Session, loading: LoadingRecordCreate) -> Tuple[Optional[LoadingRecord], str]:
    try:
        can_load, message = can_load_batch(db, loading.batch_id, lock=True)
        if not can_load:
            db.rollback()
            return None, message
        
        db_loading = LoadingRecord(**loading.model_dump())
        db.add(db_loading)
        
        batch = db.query(BrickBatch).filter(BrickBatch.id == loading.batch_id).with_for_update().first()
        if batch:
            batch.status = 'loaded'
        
        db.commit()
        db.refresh(db_loading)
        return db_loading, "装车成功"
    except Exception as e:
        db.rollback()
        return None, f"装车失败：{str(e)}"

def get_loading_records(db: Session, skip: int = 0, limit: int = 100) -> List[LoadingRecord]:
    return db.query(LoadingRecord).order_by(LoadingRecord.loading_time.desc()).offset(skip).limit(limit).all()

def get_flue_collapse_events(db: Session, firing_id: Optional[int] = None) -> List[FlueCollapseEvent]:
    query = db.query(FlueCollapseEvent).order_by(FlueCollapseEvent.start_time.desc())
    if firing_id:
        query = query.filter(FlueCollapseEvent.firing_id == firing_id)
    return query.all()

def scan_flue_collapse(db: Session) -> List[dict]:
    now = datetime.utcnow()
    events_detected = []
    
    active_firings = db.query(Firing).filter(
        Firing.status.in_(['loading', 'firing', 'cooling'])
    ).all()
    
    for firing in active_firings:
        plan_time = firing.plan_temp_time
        half_hour_before = plan_time - timedelta(minutes=30)
        one_hour_before_half = half_hour_before - timedelta(hours=1)
        
        if now < one_hour_before_half:
            continue
        
        for segment in range(1, 6):
            window_start = half_hour_before - timedelta(hours=1)
            window_end = half_hour_before
            
            avg_result = db.query(func.avg(TemperatureReading.temperature)).filter(
                TemperatureReading.firing_id == firing.id,
                TemperatureReading.segment == segment,
                TemperatureReading.recorded_at.between(window_start, window_end)
            ).scalar()
            
            if avg_result is None:
                continue
            
            avg_temp = float(avg_result)
            threshold = avg_temp - 35.0
            
            readings = db.query(TemperatureReading).filter(
                TemperatureReading.firing_id == firing.id,
                TemperatureReading.segment == segment,
                TemperatureReading.recorded_at >= half_hour_before,
                TemperatureReading.recorded_at <= plan_time,
                TemperatureReading.temperature < threshold
            ).order_by(TemperatureReading.recorded_at.asc()).all()
            
            if len(readings) >= 12:
                consecutive_groups = []
                current_group = [readings[0]]
                
                for i in range(1, len(readings)):
                    diff = (readings[i].recorded_at - readings[i-1].recorded_at).total_seconds()
                    if diff <= 90:
                        current_group.append(readings[i])
                    else:
                        if len(current_group) >= 12:
                            consecutive_groups.append(current_group)
                        current_group = [readings[i]]
                
                if len(current_group) >= 12:
                    consecutive_groups.append(current_group)
                
                for group in consecutive_groups:
                    duration = (group[-1].recorded_at - group[0].recorded_at).total_seconds() / 60
                    if duration >= 12:
                        avg_drop = sum(float(r.temperature) for r in group) / len(group)
                        temp_drop = avg_temp - avg_drop
                        
                        existing_event = db.query(FlueCollapseEvent).filter(
                            FlueCollapseEvent.firing_id == firing.id,
                            FlueCollapseEvent.segment == segment,
                            FlueCollapseEvent.end_time.is_(None),
                            func.abs(func.extract('epoch', FlueCollapseEvent.start_time - group[0].recorded_at)) < 60
                        ).first()
                        
                        if not existing_event:
                            existing_order = db.query(WorkOrder).filter(
                                WorkOrder.firing_id == firing.id,
                                WorkOrder.segment == segment,
                                WorkOrder.order_type == 'flue_collapse',
                                WorkOrder.status != 'closed'
                            ).first()
                            
                            if not existing_order:
                                order = WorkOrder(
                                    firing_id=firing.id,
                                    order_type='flue_collapse',
                                    description=f"窑道{firing.kiln_number}第{segment}段烟道疑似塌陷！温度较前一小时均值低{temp_drop:.1f}°C，持续{duration:.0f}分钟",
                                    status='open',
                                    segment=segment
                                )
                                db.add(order)
                                db.flush()
                                order_id = order.id
                            else:
                                order_id = existing_order.id
                            
                            event = FlueCollapseEvent(
                                firing_id=firing.id,
                                segment=segment,
                                start_time=group[0].recorded_at,
                                avg_temp_drop=Decimal(str(temp_drop)),
                                duration_minutes=int(duration),
                                work_order_id=order_id
                            )
                            db.add(event)
                            
                            events_detected.append({
                                'firing_id': firing.id,
                                'kiln_number': firing.kiln_number,
                                'segment': segment,
                                'start_time': group[0].recorded_at,
                                'avg_temp_drop': temp_drop,
                                'duration_minutes': duration,
                                'work_order_id': order_id
                            })
                        else:
                            existing_event.duration_minutes = int(duration)
                            existing_event.avg_temp_drop = Decimal(str(temp_drop))
                            
                            if existing_event.work_order:
                                existing_event.work_order.description = (
                                    f"窑道{firing.kiln_number}第{segment}段烟道疑似塌陷！温度较前一小时均值低{temp_drop:.1f}°C，持续{duration:.0f}分钟"
                                )
        
        db.commit()
    
    return events_detected
