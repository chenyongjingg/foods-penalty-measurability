"""Shared utilities: config, paths, logging, HTTP with compliance rate limits."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import time
from datetime import date, datetime, timezone
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def root_dir() -> Path:
    return Path(os.environ.get("FOODS_ROOT", REPO_ROOT))


def load_yaml(rel: str) -> dict:
    p = Path(rel)
    if not p.is_absolute():
        p = root_dir() / rel
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def settings() -> dict:
    return load_yaml("config/settings.yaml")


def cfg(path: str, default=None):
    cur: Any = settings()
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def path_of(key: str) -> Path:
    p = Path(cfg(f"paths.{key}", str(root_dir() / key)))
    if not p.is_absolute():
        p = root_dir() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def as_date(s) -> date | None:
    """Parse the date formats the sources actually emit.

    openFDA reports `report_date` as YYYYMMDD; the CFWS portal emits
    YYYY-MM-DD.  `date.fromisoformat` accepts the basic form only from
    Python 3.11, and the pod runs 3.10, so a naive call silently drops every
    openFDA record from any date-based analysis.  Returns None rather than
    guessing when the string is not a date.
    """
    raw = str(s or "").strip()[:10]
    if len(raw) == 8 and raw.isdigit():
        raw = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_LOG_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logdir = path_of("logs")
    fh = RotatingFileHandler(logdir / "pipeline.log", maxBytes=20_000_000, backupCount=5,
                             encoding="utf-8")
    fh.setFormatter(logging.Formatter(_LOG_FMT))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(_LOG_FMT))
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.propagate = False
    return logger


class RateLimiter:
    """Per-host spacing. Government sites default to 1 request / 2 s (Plan §5.3)."""

    def __init__(self, seconds: float):
        self.seconds = max(0.0, float(seconds))
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> None:
        if self.seconds <= 0:
            return
        now = time.monotonic()
        last = self._last.get(host, 0.0)
        delay = self.seconds - (now - last)
        if delay > 0:
            time.sleep(delay + random.uniform(0, 0.15))
        self._last[host] = time.monotonic()


def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": cfg("runtime.user_agent"),
                      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    return s


def http_request(session: requests.Session, method: str, url: str,
                 rate: RateLimiter | None = None, **kwargs) -> requests.Response:
    """Retry with exponential backoff; never bypass access controls."""
    retries = int(cfg("runtime.retries", 3))
    base = float(cfg("runtime.backoff_base", 2.0))
    timeout = kwargs.pop("timeout", cfg("runtime.http_timeout", 30))
    host = re.sub(r"^https?://([^/]+).*", r"\1", url)
    last_exc = None
    for attempt in range(retries + 1):
        if rate:
            rate.wait(host)
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(base ** attempt + random.uniform(0, 0.5))
                continue
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(base ** attempt + random.uniform(0, 0.5))
                continue
            raise
    raise last_exc  # pragma: no cover


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def normalize_space(s: str) -> str:
    s = s.replace(" ", " ").replace("　", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", s).strip()


def disk_free_pct() -> float:
    total, used, free = shutil.disk_usage(root_dir())
    return 100.0 * free / total


def guard_disk(logger: logging.Logger) -> None:
    pct = disk_free_pct()
    if pct < (100 - float(cfg("runtime.disk_clean_pct", 95))):
        tmp = path_of("data") / "tmp"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
            logger.warning("disk guard: purged data/tmp (free=%.1f%%)", pct)
    if pct < (100 - float(cfg("runtime.disk_warn_pct", 80))):
        logger.error("disk warning: free=%.1f%% below threshold", pct)
