from datetime import datetime, timedelta
from decimal import Decimal
import random
import sys

from database import SessionLocal, engine
from models import Base, Firing, TemperatureReading, BrickBatch, WorkOrder, FlueCollapseEvent
from crud import scan_flue_collapse

def seed_demo_data():
    db = SessionLocal()
    try:
        print("开始生成演示数据...")
        
        now = datetime.utcnow()
        
        firings_data = [
            {
                "kiln_number": "K-001",
                "plan_temp_time": now + timedelta(hours=2),
                "status": "firing",
                "start_time": now - timedelta(hours=3),
            },
            {
                "kiln_number": "K-002",
                "plan_temp_time": now - timedelta(minutes=10),
                "status": "cooling",
                "start_time": now - timedelta(hours=2),
            },
            {
                "kiln_number": "K-003",
                "plan_temp_time": now - timedelta(hours=1),
                "status": "cooling",
                "start_time": now - timedelta(hours=5),
            },
            {
                "kiln_number": "K-004",
                "plan_temp_time": now - timedelta(hours=4),
                "status": "completed",
                "start_time": now - timedelta(hours=8),
                "end_time": now - timedelta(minutes=30),
            },
            {
                "kiln_number": "K-005",
                "plan_temp_time": now + timedelta(hours=6),
                "status": "loading",
            },
        ]
        
        created_firings = []
        for fd in firings_data:
            firing = Firing(**fd)
            db.add(firing)
            db.flush()
            created_firings.append(firing)
            print(f"  创建窑次: {firing.kiln_number} (ID: {firing.id}, 状态: {firing.status})")
        
        db.commit()
        
        print("\n生成温度读数...")
        for firing in created_firings:
            if firing.status in ['loading']:
                continue
            
            base_temp = 950.0
            
            start_time = firing.start_time or (firing.plan_temp_time - timedelta(hours=4))
            end_time = min(
                firing.end_time or now,
                now
            )
            
            current_time = start_time
            minutes_count = 0
            
            while current_time <= end_time and minutes_count < 600:
                for segment in range(1, 6):
                    temp_variation = random.uniform(-15, 15)
                    
                    if firing.kiln_number == "K-002" and segment == 3:
                        time_to_plan = (firing.plan_temp_time - current_time).total_seconds() / 60
                        if 8 <= time_to_plan <= 25:
                            temp_variation = random.uniform(-50, -36)
                    
                    if firing.kiln_number == "K-003" and segment == 2:
                        time_to_plan = (firing.plan_temp_time - current_time).total_seconds() / 60
                        if 10 <= time_to_plan <= 28:
                            temp_variation = random.uniform(-45, -36)
                    
                    segment_offset = (segment - 3) * random.uniform(-5, 5)
                    if (firing.kiln_number == "K-002" and segment == 3 and 8 <= time_to_plan <= 25) or \
                       (firing.kiln_number == "K-003" and segment == 2 and 10 <= time_to_plan <= 28):
                        min_drop = 45.0 + max(0, segment_offset)
                        temperature = base_temp - random.uniform(min_drop, 60) + segment_offset
                    else:
                        temperature = base_temp + temp_variation + segment_offset
                    pressure = random.uniform(-200, -50)
                    
                    reading = TemperatureReading(
                        firing_id=firing.id,
                        segment=segment,
                        temperature=Decimal(str(round(temperature, 2))),
                        negative_pressure=Decimal(str(round(pressure, 2))),
                        recorded_at=current_time
                    )
                    db.add(reading)
                
                current_time += timedelta(minutes=1)
                minutes_count += 1
            
            print(f"  窑次 {firing.kiln_number}: 生成 {minutes_count} 分钟 × 5段 = {minutes_count * 5} 条读数")
        
        db.commit()
        
        print("\n执行烟道塌陷扫描...")
        events = scan_flue_collapse(db)
        print(f"  扫描发现 {len(events)} 个烟道塌陷事件")
        for event in events:
            print(f"    - {event['kiln_number']} 段{event['segment']}: 降温{event['avg_temp_drop']:.1f}°C")
        
        print("\n生成砖批次...")
        grades = [1, 2, 3, 4, 5]
        grade_weights = [0.05, 0.15, 0.3, 0.35, 0.15]
        
        for firing in created_firings:
            if firing.status == 'loading':
                continue
            
            num_batches = random.randint(3, 6)
            for i in range(num_batches):
                grade = random.choices(grades, weights=grade_weights)[0]
                
                if firing.kiln_number == "K-002":
                    if i == 0:
                        grade = 1
                    elif i == 1:
                        grade = 2
                
                if firing.kiln_number == "K-003":
                    if i == 0:
                        grade = 2
                
                batch = BrickBatch(
                    firing_id=firing.id,
                    batch_code=f"{firing.kiln_number}-B{i+1:03d}",
                    color_grade=grade,
                    warpage_mm=Decimal(str(round(random.uniform(0.5, 8.0), 2))),
                    status='produced'
                )
                db.add(batch)
                db.flush()
                
                from crud import check_and_create_rework_order
                check_and_create_rework_order(db, batch)
                
                print(f"  窑次 {firing.kiln_number}: 批次 {batch.batch_code}, 品级 {grade}, 翘曲 {batch.warpage_mm}mm")
        
        db.commit()
        
        loaded_batch = db.query(BrickBatch).filter(
            BrickBatch.firing_id == 4
        ).first()
        if loaded_batch:
            from crud import create_loading_record
            from schemas import LoadingRecordCreate
            loading = LoadingRecordCreate(
                batch_id=loaded_batch.id,
                vehicle_plate="京A12345",
                operator="张三",
                quantity=500,
                remarks="正常出库"
            )
            create_loading_record(db, loading)
            print(f"\n  创建装车记录: 批次 {loaded_batch.batch_code}")
        
        db.commit()
        
        print("\n" + "="*50)
        print("演示数据生成完成！")
        print(f"  窑次总数: {len(created_firings)}")
        print(f"  温度读数: {db.query(TemperatureReading).count()} 条")
        print(f"  砖批次: {db.query(BrickBatch).count()} 批")
        print(f"  工单: {db.query(WorkOrder).count()} 个")
        print(f"  烟道塌陷事件: {db.query(FlueCollapseEvent).count()} 个")
        print("="*50)
        
    except Exception as e:
        print(f"错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
