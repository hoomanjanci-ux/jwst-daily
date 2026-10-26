CREATE TABLE IF NOT EXISTS ai_control (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_queue (product TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready',created_utc TEXT NOT NULL,slot TEXT,published_utc TEXT,synced INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_slots (slot TEXT PRIMARY KEY,start_utc TEXT NOT NULL,end_utc TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'waiting',product TEXT,completed_utc TEXT,note TEXT);
CREATE TABLE IF NOT EXISTS ai_receipts (slot TEXT NOT NULL,lang TEXT NOT NULL,part TEXT NOT NULL,status TEXT NOT NULL,ids TEXT,updated_utc TEXT NOT NULL,PRIMARY KEY(slot,lang,part));
CREATE INDEX IF NOT EXISTS ai_queue_status ON ai_queue(status,created_utc);
