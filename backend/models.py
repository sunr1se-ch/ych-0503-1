from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, Text, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Firing(Base):
    __tablename__ = 'firings'

    id = Column(Integer, primary_key=True)
    kiln_number = Column(String(20), nullable=False)
    plan_temp_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default='loading')
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    readings = relationship('TemperatureReading', back_populates='firing', cascade='all, delete-orphan')
    batches = relationship('BrickBatch', back_populates='firing', cascade='all, delete-orphan')
    work_orders = relationship('WorkOrder', back_populates='firing', cascade='all, delete-orphan')
    flue_events = relationship('FlueCollapseEvent', back_populates='firing', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint("status IN ('loading', 'firing', 'cooling', 'completed')", name='status_check'),
    )

class TemperatureReading(Base):
    __tablename__ = 'temperature_readings'

    id = Column(Integer, primary_key=True)
    firing_id = Column(Integer, ForeignKey('firings.id', ondelete='CASCADE'), nullable=False)
    segment = Column(Integer, nullable=False)
    temperature = Column(DECIMAL(6, 2), nullable=False)
    negative_pressure = Column(DECIMAL(6, 2), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    firing = relationship('Firing', back_populates='readings')

    __table_args__ = (
        UniqueConstraint('firing_id', 'segment', 'recorded_at', name='uix_firing_segment_time'),
        CheckConstraint('segment BETWEEN 1 AND 5', name='segment_check'),
        Index('idx_readings_firing_segment', 'firing_id', 'segment'),
        Index('idx_readings_recorded_at', 'recorded_at'),
    )

class BrickBatch(Base):
    __tablename__ = 'brick_batches'

    id = Column(Integer, primary_key=True)
    firing_id = Column(Integer, ForeignKey('firings.id', ondelete='CASCADE'), nullable=False)
    batch_code = Column(String(50), nullable=False)
    color_grade = Column(Integer, nullable=False)
    warpage_mm = Column(DECIMAL(5, 2), nullable=False)
    status = Column(String(20), nullable=False, default='produced')
    created_at = Column(DateTime, default=datetime.utcnow)

    firing = relationship('Firing', back_populates='batches')
    work_orders = relationship('WorkOrder', back_populates='batch')
    loading_records = relationship('LoadingRecord', back_populates='batch')

    __table_args__ = (
        UniqueConstraint('firing_id', 'batch_code', name='uix_firing_batch'),
        CheckConstraint('color_grade BETWEEN 1 AND 5', name='grade_check'),
        CheckConstraint("status IN ('produced', 'rework_pending', 'rework_done', 'loaded', 'shipped')", name='batch_status_check'),
    )

class WorkOrder(Base):
    __tablename__ = 'work_orders'

    id = Column(Integer, primary_key=True)
    firing_id = Column(Integer, ForeignKey('firings.id', ondelete='CASCADE'), nullable=False)
    batch_id = Column(Integer, ForeignKey('brick_batches.id', ondelete='SET NULL'))
    order_type = Column(String(30), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='open')
    segment = Column(Integer)
    detected_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)
    closed_by = Column(String(100))

    firing = relationship('Firing', back_populates='work_orders')
    batch = relationship('BrickBatch', back_populates='work_orders')
    flue_events = relationship('FlueCollapseEvent', back_populates='work_order')

    __table_args__ = (
        CheckConstraint("order_type IN ('flue_collapse', 'rework')", name='order_type_check'),
        CheckConstraint("status IN ('open', 'in_progress', 'closed')", name='order_status_check'),
        CheckConstraint('segment BETWEEN 1 AND 5', name='order_segment_check'),
        Index('idx_orders_firing', 'firing_id'),
        Index('idx_orders_status', 'status'),
    )

class LoadingRecord(Base):
    __tablename__ = 'loading_records'

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('brick_batches.id'), nullable=False)
    vehicle_plate = Column(String(20), nullable=False)
    loading_time = Column(DateTime, default=datetime.utcnow)
    operator = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    remarks = Column(Text)

    batch = relationship('BrickBatch', back_populates='loading_records')

class FlueCollapseEvent(Base):
    __tablename__ = 'flue_collapse_events'

    id = Column(Integer, primary_key=True)
    firing_id = Column(Integer, ForeignKey('firings.id', ondelete='CASCADE'), nullable=False)
    segment = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    avg_temp_drop = Column(DECIMAL(6, 2), nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=0)
    work_order_id = Column(Integer, ForeignKey('work_orders.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.utcnow)

    firing = relationship('Firing', back_populates='flue_events')
    work_order = relationship('WorkOrder', back_populates='flue_events')

    __table_args__ = (
        CheckConstraint('segment BETWEEN 1 AND 5', name='flue_segment_check'),
    )
