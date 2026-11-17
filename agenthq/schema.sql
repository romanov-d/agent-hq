-- Agent HQ database. One SQLite file for every project on this machine.
-- Default location: ~/.agent-hq/agent-hq.db (override with AGENTHQ_DB).
-- Migrations are additive only: new columns via ALTER TABLE, never DROP.

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS projects (
  id          INTEGER PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  path        TEXT,                        -- absolute folder on disk
  status      TEXT DEFAULT 'active',       -- active | paused | done | archive
  section     TEXT DEFAULT 'other',        -- site | app | mobile | bot | game | lib | infra | content | other
  kind        TEXT DEFAULT 'own',          -- own | client
  client      TEXT DEFAULT '',
  priority    INTEGER DEFAULT 2,           -- 0 urgent .. 3 someday
  summary     TEXT DEFAULT '',             -- one line, shown in lists
  note        TEXT DEFAULT '',             -- "where we left off", updated by every result entry
  parent_id   INTEGER REFERENCES projects(id),
  created_at  TEXT,
  updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER REFERENCES projects(id),
  parent_id   INTEGER REFERENCES tasks(id),
  title       TEXT NOT NULL,
  body        TEXT DEFAULT '',             -- context + acceptance criteria
  status      TEXT DEFAULT 'todo',         -- todo | doing | review | blocked | done | drop
  priority    INTEGER DEFAULT 2,
  assignee    TEXT DEFAULT '',             -- '' | me | claude | any agent name
  due         TEXT,                        -- YYYY-MM-DD
  blocked_by  TEXT DEFAULT '',             -- what we are waiting for
  created_by  TEXT DEFAULT 'me',
  created_at  TEXT,
  started_at  TEXT,
  done_at     TEXT,
  position    REAL DEFAULT 0               -- manual order inside a status column
);

CREATE TABLE IF NOT EXISTS entries (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  project_id  INTEGER REFERENCES projects(id),
  task_id     INTEGER REFERENCES tasks(id),
  kind        TEXT DEFAULT 'note',         -- note | result | decision | blocker
  text        TEXT NOT NULL,
  actor       TEXT DEFAULT 'me',
  session_id  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER REFERENCES projects(id),
  session_id  TEXT,
  cwd         TEXT,
  started_at  TEXT,
  ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS deals (
  id          INTEGER PRIMARY KEY,
  client      TEXT NOT NULL,
  title       TEXT DEFAULT '',
  project_id  INTEGER REFERENCES projects(id),
  amount      REAL DEFAULT 0,
  currency    TEXT DEFAULT 'USD',
  stage       TEXT DEFAULT 'lead',         -- lead | talk | proposal | won | invoiced | paid | lost
  next_action TEXT DEFAULT '',
  next_at     TEXT,
  created_at  TEXT,
  updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS payments (
  id          INTEGER PRIMARY KEY,
  deal_id     INTEGER REFERENCES deals(id),
  amount      REAL NOT NULL,
  currency    TEXT DEFAULT 'USD',
  paid_at     TEXT,
  note        TEXT DEFAULT ''
);

-- Folders the user removed from Agent HQ, so auto-registration never re-adds them.
CREATE TABLE IF NOT EXISTS ignored (
  path        TEXT PRIMARY KEY,
  at          TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key         TEXT PRIMARY KEY,
  value       TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent  ON tasks(parent_id);
CREATE INDEX IF NOT EXISTS idx_entries_proj  ON entries(project_id, ts);
CREATE INDEX IF NOT EXISTS idx_sessions_sid  ON sessions(session_id);
