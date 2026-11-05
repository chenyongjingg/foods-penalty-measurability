"""SQLite manifest state machine: raw -> clean -> labeled -> extracted -> analyzed.

Plan §5.3: every document carries its stage; a crash resumes from the last
committed stage. Transitions are guarded so a stage can never skip forward.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .common import get_logger, path_of, utc_iso

STAGES = ["raw", "clean", "labeled", "extracted", "analyzed"]
TERMINAL_OFF_PATH = {"filtered_out", "duplicate", "failed"}


class Manifest:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (path_of("state") / "foods.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = get_logger("manifest")
        self._init()

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.db_path, timeout=60)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            yield c
            c.commit()
        finally:
            c.close()

    def _init(self) -> None:
        with self.conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS docs (
                doc_id     TEXT PRIMARY KEY,
                source     TEXT NOT NULL,
                native_id  TEXT,
                url        TEXT,
                title      TEXT,
                published  TEXT,
                fetched_at TEXT,
                stage      TEXT NOT NULL,
                lang       TEXT,
                raw_path   TEXT,
                text_path  TEXT,
                text_sha   TEXT,
                n_chars    INTEGER,
                meta       TEXT,
                error      TEXT,
                attempts   INTEGER DEFAULT 0,
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_docs_stage ON docs(stage);
            CREATE INDEX IF NOT EXISTS idx_docs_source ON docs(source);
            CREATE TABLE IF NOT EXISTS runs (
                run_id    TEXT PRIMARY KEY,
                stage     TEXT,
                started   TEXT,
                finished  TEXT,
                status    TEXT,
                stats     TEXT
            );
            CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS dedupe (k TEXT PRIMARY KEY, doc_id TEXT, at TEXT);
            CREATE TABLE IF NOT EXISTS stage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT, from_stage TEXT, to_stage TEXT, at TEXT, note TEXT
            );
            """)

    # ---------- docs ----------
    def upsert_raw(self, *, doc_id: str, source: str, native_id: str | None,
                   url: str | None, title: str | None, published: str | None,
                   raw_path: str | None, meta: dict | None = None) -> bool:
        """Insert a raw doc. Returns True if newly inserted."""
        now = utc_iso()
        with self.conn() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO docs(doc_id,source,native_id,url,title,published,"
                "fetched_at,stage,raw_path,meta,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, source, native_id, url, title, published, now, "raw",
                 raw_path, json.dumps(meta or {}, ensure_ascii=False), now))
            inserted = cur.rowcount == 1
            if inserted:
                c.execute("INSERT INTO stage_log(doc_id,from_stage,to_stage,at,note) "
                          "VALUES(?,?,?,?,?)", (doc_id, None, "raw", now, "collected"))
            return inserted

    def exists(self, doc_id: str) -> bool:
        with self.conn() as c:
            return c.execute("SELECT 1 FROM docs WHERE doc_id=?", (doc_id,)).fetchone() is not None

    def get(self, doc_id: str) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
            return dict(row) if row else None

    def set_stage(self, doc_id: str, stage: str, *, text_path: str | None = None,
                  text_sha: str | None = None, n_chars: int | None = None,
                  lang: str | None = None, error: str | None = None,
                  note: str | None = None) -> None:
        if stage not in STAGES + list(TERMINAL_OFF_PATH):
            raise ValueError(f"unknown stage {stage}")
        with self.conn() as c:
            old = c.execute("SELECT stage FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
            c.execute("""UPDATE docs SET stage=?, updated_at=?,
                         text_path=COALESCE(?,text_path), text_sha=COALESCE(?,text_sha),
                         n_chars=COALESCE(?,n_chars), lang=COALESCE(?,lang),
                         error=? WHERE doc_id=?""",
                      (stage, utc_iso(), text_path, text_sha, n_chars, lang, error, doc_id))
            if old and old["stage"] != stage:
                c.execute("INSERT INTO stage_log(doc_id,from_stage,to_stage,at,note) "
                          "VALUES(?,?,?,?,?)", (doc_id, old["stage"], stage, utc_iso(), note))

    def update_raw(self, doc_id: str, *, raw_path: str | None = None,
                   meta: dict | None = None) -> None:
        with self.conn() as c:
            c.execute("""UPDATE docs SET raw_path=COALESCE(?,raw_path),
                         meta=COALESCE(?,meta), updated_at=? WHERE doc_id=?""",
                      (raw_path, json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                       utc_iso(), doc_id))

    def bump_attempt(self, doc_id: str, error: str | None = None) -> None:
        with self.conn() as c:
            c.execute("UPDATE docs SET attempts=attempts+1, error=?, updated_at=? WHERE doc_id=?",
                      (error, utc_iso(), doc_id))

    def iter_stage(self, stage: str, limit: int | None = None,
                   source: str | None = None) -> Iterator[dict]:
        q = "SELECT * FROM docs WHERE stage=?"
        args: list = [stage]
        if source:
            q += " AND source=?"
            args.append(source)
        q += " ORDER BY fetched_at"
        if limit:
            q += f" LIMIT {int(limit)}"
        with self.conn() as c:
            for row in c.execute(q, args):
                yield dict(row)

    def counts(self) -> dict:
        with self.conn() as c:
            rows = c.execute("SELECT source, stage, COUNT(*) n FROM docs GROUP BY source, stage").fetchall()
        out: dict = {}
        for r in rows:
            out.setdefault(r["source"], {})[r["stage"]] = r["n"]
        return out

    def total(self, stage: str | None = None) -> int:
        with self.conn() as c:
            if stage:
                return c.execute("SELECT COUNT(*) FROM docs WHERE stage=?", (stage,)).fetchone()[0]
            return c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]

    def dedupe_claim(self, key: str, doc_id: str) -> bool:
        """Atomically claim a dedupe key. False if already claimed by another doc."""
        with self.conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO dedupe(k,doc_id,at) VALUES(?,?,?)",
                            (key, doc_id, utc_iso()))
            return cur.rowcount == 1

    # ---------- kv / runs ----------
    def kv_set(self, k: str, v) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                      (k, json.dumps(v, ensure_ascii=False)))

    def kv_get(self, k: str, default=None):
        with self.conn() as c:
            row = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
            return json.loads(row["v"]) if row else default

    def run_start(self, run_id: str, stage: str) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO runs(run_id,stage,started,status) VALUES(?,?,?,?)",
                      (run_id, stage, utc_iso(), "running"))

    def run_finish(self, run_id: str, status: str, stats: dict) -> None:
        with self.conn() as c:
            c.execute("UPDATE runs SET finished=?, status=?, stats=? WHERE run_id=?",
                      (utc_iso(), status, json.dumps(stats, ensure_ascii=False), run_id))
