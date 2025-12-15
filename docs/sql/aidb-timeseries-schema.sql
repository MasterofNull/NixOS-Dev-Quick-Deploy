-- Shared schema for rf_signals / market_data / network_events tables.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS rf_signals (
    time            TIMESTAMPTZ       NOT NULL,
    frequency_hz    NUMERIC,
    power_dbm       NUMERIC,
    bandwidth_hz    NUMERIC,
    modulation      TEXT,
    station_id      TEXT,
    metadata        JSONB             DEFAULT '{}'::jsonb
);
SELECT create_hypertable('rf_signals', 'time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS market_data (
    time        TIMESTAMPTZ   NOT NULL,
    symbol      TEXT          NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      BIGINT,
    metadata    JSONB         DEFAULT '{}'::jsonb
);
SELECT create_hypertable('market_data', 'time', partitioning_column => 'symbol', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS network_events (
    time            TIMESTAMPTZ   NOT NULL,
    event_id        UUID          DEFAULT uuid_generate_v4(),
    source_ip       INET,
    destination_ip  INET,
    protocol        TEXT,
    event_type      TEXT,
    severity        TEXT,
    metadata        JSONB         DEFAULT '{}'::jsonb,
    PRIMARY KEY (event_id)
);
SELECT create_hypertable('network_events', 'time', if_not_exists => TRUE);
