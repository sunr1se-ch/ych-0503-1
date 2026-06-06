CREATE TABLE IF NOT EXISTS firings (
    id SERIAL PRIMARY KEY,
    kiln_number VARCHAR(20) NOT NULL,
    plan_temp_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'loading',
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT status_check CHECK (status IN ('loading', 'firing', 'cooling', 'completed'))
);

CREATE TABLE IF NOT EXISTS temperature_readings (
    id SERIAL PRIMARY KEY,
    firing_id INTEGER NOT NULL REFERENCES firings(id) ON DELETE CASCADE,
    segment INTEGER NOT NULL CHECK (segment BETWEEN 1 AND 5),
    temperature DECIMAL(6,2) NOT NULL,
    negative_pressure DECIMAL(6,2) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(firing_id, segment, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_readings_firing_segment ON temperature_readings(firing_id, segment);
CREATE INDEX IF NOT EXISTS idx_readings_recorded_at ON temperature_readings(recorded_at);

CREATE TABLE IF NOT EXISTS brick_batches (
    id SERIAL PRIMARY KEY,
    firing_id INTEGER NOT NULL REFERENCES firings(id) ON DELETE CASCADE,
    batch_code VARCHAR(50) NOT NULL,
    color_grade INTEGER NOT NULL CHECK (color_grade BETWEEN 1 AND 5),
    warpage_mm DECIMAL(5,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'produced',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(firing_id, batch_code),
    CONSTRAINT batch_status_check CHECK (status IN ('produced', 'rework_pending', 'rework_done', 'loaded', 'shipped'))
);

CREATE TABLE IF NOT EXISTS work_orders (
    id SERIAL PRIMARY KEY,
    firing_id INTEGER NOT NULL REFERENCES firings(id) ON DELETE CASCADE,
    batch_id INTEGER REFERENCES brick_batches(id) ON DELETE SET NULL,
    order_type VARCHAR(30) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    segment INTEGER CHECK (segment BETWEEN 1 AND 5),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    closed_by VARCHAR(100),
    CONSTRAINT order_type_check CHECK (order_type IN ('flue_collapse', 'rework')),
    CONSTRAINT order_status_check CHECK (status IN ('open', 'in_progress', 'closed'))
);

CREATE INDEX IF NOT EXISTS idx_orders_firing ON work_orders(firing_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON work_orders(status);

CREATE TABLE IF NOT EXISTS loading_records (
    id SERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES brick_batches(id),
    vehicle_plate VARCHAR(20) NOT NULL,
    loading_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operator VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS flue_collapse_events (
    id SERIAL PRIMARY KEY,
    firing_id INTEGER NOT NULL REFERENCES firings(id) ON DELETE CASCADE,
    segment INTEGER NOT NULL CHECK (segment BETWEEN 1 AND 5),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    avg_temp_drop DECIMAL(6,2) NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    work_order_id INTEGER REFERENCES work_orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
