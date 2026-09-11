-- PANO GOZ storage schema.
--
-- ONE driver executes this: SQLite.  It is nevertheless written in portable SQL
-- so that the intended TimescaleDB path can execute it unchanged.  That path is
-- NOT built: there is no schema_timescale.sql, no hypertable, compression or
-- continuous-aggregate statement anywhere in this repository, and no bulk COPY
-- write path.  See panogoz/store/db.py.
--
-- Sizing (measured assumptions, not asserted ones):
--   ~120 series per panel at 1/min  = 2.0 points/s = 172 800 points/panel/day
--   100 panels                      = 200 points/s = 17.28 M points/day
-- Retention: 90 d raw, 2 y 5-minute rollup, 10 y hourly rollup ~ 18 GB steady
-- state at the labelled 2.5 B/point compression assumption (docs/01 §5.2).
-- A 500 GB NVMe is more than 25x headroom, so the on-premise constraint costs
-- essentially nothing in storage.  That is worth saying out loud.

PRAGMA journal_mode = WAL;

-- Removed only after broker PUBACK; separate from measurement retention.
CREATE TABLE IF NOT EXISTS gateway_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_key TEXT NOT NULL,
    payload BLOB NOT NULL,
    retain INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS gateway_outbox_panel ON gateway_outbox(panel_key, id);
CREATE TABLE IF NOT EXISTS gateway_boot (
    panel_key TEXT PRIMARY KEY,
    boot INTEGER NOT NULL
);

-- ---------------------------------------------------------------- assets ---

CREATE TABLE IF NOT EXISTS panel (
    panel_key      TEXT PRIMARY KEY,          -- "<site>/<panel>"
    panel_index    INTEGER NOT NULL UNIQUE,   -- 1-based, drives the Modbus block
    site           TEXT NOT NULL,
    name           TEXT NOT NULL,
    dso            TEXT NOT NULL,             -- ADM | GDZ
    lat            REAL,
    lon            REAL,
    rated_kva      REAL NOT NULL DEFAULT 1600,
    commissioned   REAL,                      -- epoch seconds
    learn_until    REAL,                      -- alarms arm after this instant
    has_analyser   INTEGER NOT NULL DEFAULT 1, -- TEDAS Madde 2.2.11 option 1 vs 2
    has_arc_relay  INTEGER NOT NULL DEFAULT 1, -- ABB TVOC-2 fitted?
    arc_detectors  INTEGER NOT NULL DEFAULT 0,
    notes          TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS device (
    panel_key   TEXT NOT NULL,
    device_key  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    fw          TEXT DEFAULT '',
    last_seen   REAL,
    boot        INTEGER DEFAULT 0,
    seq         INTEGER DEFAULT 0,
    rssi_dbm    REAL,
    battery_v   REAL,
    battery_pct REAL,
    faults      TEXT DEFAULT '',              -- comma separated flag names
    PRIMARY KEY (panel_key, device_key)
);

CREATE TABLE IF NOT EXISTS joint (
    panel_key    TEXT NOT NULL,
    joint_key    TEXT NOT NULL,
    label        TEXT NOT NULL,
    zone         TEXT NOT NULL,
    conductor    TEXT NOT NULL,
    feeder_index INTEGER,
    rated_a      REAL NOT NULL,
    sibling_group TEXT NOT NULL,
    monitored    INTEGER NOT NULL DEFAULT 0,
    x_mm         REAL, y_mm REAL,
    PRIMARY KEY (panel_key, joint_key)
);

-- ------------------------------------------------------------ timeseries ---

-- Panel-level channels (environment, analyser, arc relay, device health).
CREATE TABLE IF NOT EXISTS sample (
    ts         REAL NOT NULL,
    panel_key  TEXT NOT NULL,
    channel    TEXT NOT NULL,
    value      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sample ON sample (panel_key, channel, ts);

-- Per-joint channels (temperature, current, theta and friends).  Kept in its
-- own table because it is the hot path: 40 monitored joints x 8 channels is
-- where the volume and every interesting query lives.
CREATE TABLE IF NOT EXISTS joint_sample (
    ts         REAL NOT NULL,
    panel_key  TEXT NOT NULL,
    joint_key  TEXT NOT NULL,
    channel    TEXT NOT NULL,
    value      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_joint_sample ON joint_sample (panel_key, joint_key, channel, ts);

-- Daily rollup the CUSUM actually runs on.  theta is noisy minute to minute;
-- the drift we hunt is 0.2 K/week, so the detector consumes daily medians.
CREATE TABLE IF NOT EXISTS joint_daily (
    day         INTEGER NOT NULL,             -- days since epoch
    panel_key   TEXT NOT NULL,
    joint_key   TEXT NOT NULL,
    theta_med   REAL,
    theta_p90   REAL,
    n           INTEGER,
    load_mean   REAL,
    sens_pct    REAL,
    -- The CUSUM value as it stood at the end of that day, and the baseline it
    -- was measured against.  Stored rather than recomputed because this is the
    -- series an operator is shown when asked to believe a finding: the raw
    -- theta samples are pruned after 90 days, but the evidence for a decision
    -- taken last spring has to survive as long as the decision does.
    cusum       REAL,
    baseline    REAL,
    theta_min   REAL,
    PRIMARY KEY (day, panel_key, joint_key)
);

-- ------------------------------------------------------------- detector ----

CREATE TABLE IF NOT EXISTS joint_state (
    panel_key    TEXT NOT NULL,
    joint_key    TEXT NOT NULL,
    theta        REAL DEFAULT 0,
    theta_p      REAL DEFAULT 100,            -- RLS covariance
    dt_excess    REAL DEFAULT 0,              -- filtered excess, for the lag model
    tau_s        REAL DEFAULT 1200,
    resid_ewma   REAL DEFAULT 0,
    cusum_pos    REAL DEFAULT 0,
    cusum_neg    REAL DEFAULT 0,
    train_n      INTEGER DEFAULT 0,
    train_mean   REAL DEFAULT 0,
    train_m2     REAL DEFAULT 0,
    baseline     REAL,
    sigma        REAL,
    slope        REAL DEFAULT 0,
    changepoint  REAL,                        -- epoch seconds of detected onset
    alarm_days   INTEGER DEFAULT 0,           -- consecutive qualifying days
    excess_r_uohm REAL,
    updated_at   REAL,
    PRIMARY KEY (panel_key, joint_key)
);

CREATE TABLE IF NOT EXISTS panel_state (
    panel_key      TEXT PRIMARY KEY,
    health_index   REAL DEFAULT 100,
    severity       TEXT DEFAULT 'BILGI',
    status_flags   TEXT DEFAULT '',
    risks          TEXT DEFAULT '{}',         -- JSON {mode: risk}
    theta_max      REAL DEFAULT 0,
    theta_max_joint TEXT,
    sensitivity    REAL DEFAULT 0,
    load_factor    REAL DEFAULT 0,
    updated_at     REAL,
    payload        TEXT DEFAULT '{}'          -- JSON live image for the UI and ICD
);

-- --------------------------------------------------------------- alarms ----

CREATE TABLE IF NOT EXISTS incident (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_key     TEXT NOT NULL,
    joint_key     TEXT,
    mode          TEXT NOT NULL,              -- failure mode key
    severity      TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'ACIK',  -- ACIK | ONAYLANDI | KAPANDI
    opened_at     REAL NOT NULL,
    updated_at    REAL NOT NULL,
    closed_at     REAL,
    acked_at      REAL,
    acked_by      TEXT,
    ack_token     TEXT,
    title         TEXT NOT NULL,
    evidence      TEXT NOT NULL DEFAULT '{}', -- JSON: the "why" block
    ruled_out     TEXT NOT NULL DEFAULT '[]', -- JSON: confounders excluded
    action        TEXT NOT NULL DEFAULT '',
    dispatched    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_incident_open ON incident (state, severity, opened_at);
CREATE INDEX IF NOT EXISTS idx_incident_panel ON incident (panel_key, opened_at);

-- Every alarm we deliberately did NOT raise, with its reason.  This table is a
-- product feature, not a debug log: it is what an operator looks at when they
-- ask "why didn't you tell me about that 78 degree reading?".
CREATE TABLE IF NOT EXISTS suppression (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL NOT NULL,
    panel_key  TEXT NOT NULL,
    joint_key  TEXT,
    mode       TEXT,
    reason     TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_suppression ON suppression (ts, panel_key);

CREATE TABLE IF NOT EXISTS notification (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    ts          REAL NOT NULL,
    channel     TEXT NOT NULL,                -- SMS | SESLI | MATRIX | EPOSTA
    target      TEXT NOT NULL,
    body        TEXT NOT NULL,
    state       TEXT NOT NULL,                -- KUYRUKTA | GONDERILDI | ILETILDI | HATA
    transcript  TEXT DEFAULT ''               -- the actual AT/SMPP exchange
);

-- Append-only, hash-chained.  Each row commits to the previous one, so a
-- deletion or edit anywhere in the history is detectable.
CREATE TABLE IF NOT EXISTS audit (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    subject   TEXT NOT NULL DEFAULT '',
    detail    TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT NOT NULL DEFAULT '',
    hash      TEXT NOT NULL
);

-- ---------------------------------------------------------------- PRPD -----

CREATE TABLE IF NOT EXISTS prpd (
    ts        REAL NOT NULL,
    panel_key TEXT NOT NULL,
    device    TEXT NOT NULL,
    klass     TEXT NOT NULL,
    features  TEXT NOT NULL DEFAULT '{}',
    hist      BLOB NOT NULL,                  -- 64 phase x 32 amplitude, uint16
    PRIMARY KEY (ts, panel_key, device)
);
