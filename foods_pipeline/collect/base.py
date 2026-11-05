"""Collector base: raw append-only storage + manifest registration."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import cfg, get_logger, http_session, path_of, sha256_text, utc_iso
from ..manifest import Manifest


class Collector:
    source = "base"

    def __init__(self, manifest: Manifest | None = None):
        self.m = manifest or Manifest()
        self.log = get_logger(f"collect.{self.source}")
        self.s = http_session()
        self.rate = None

    def doc_id(self, native_id: str) -> str:
        return f"{self.source}:{sha256_text(str(native_id))[:24]}"

    def raw_dir(self) -> Path:
        d = path_of("data") / "raw" / self.source
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_raw(self, doc_id: str, ext: str, payload: bytes | str) -> str:
        day = utc_iso()[:10].replace("-", "")
        d = self.raw_dir() / day
        d.mkdir(parents=True, exist_ok=True)
        safe = doc_id.split(":", 1)[-1]
        p = d / f"{safe}.{ext}"
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        p.write_bytes(payload)
        return str(p)

    def register(self, *, doc_id: str, native_id: str, url: str | None,
                 title: str | None, published: str | None, raw_path: str | None,
                 meta: dict | None = None) -> bool:
        return self.m.upsert_raw(doc_id=doc_id, source=self.source, native_id=native_id,
                                 url=url, title=title, published=published,
                                 raw_path=raw_path, meta=meta or {})

    def dump_meta(self, meta: dict) -> str:
        return json.dumps(meta, ensure_ascii=False)
