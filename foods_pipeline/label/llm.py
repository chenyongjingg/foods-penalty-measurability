"""OpenAI-compatible client for the local vLLM server."""
from __future__ import annotations

import json
import re
import threading
import time

import requests

from ..common import cfg, get_logger


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: int = 300):
        self.base = (base_url or cfg("llm.base_url")).rstrip("/")
        self.key = api_key or cfg("llm.api_key", "EMPTY")
        self.timeout = timeout
        self.log = get_logger("llm")
        # requests.Session is not thread-safe; the labeler uses a worker pool.
        self._local = threading.local()

    @property
    def s(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            self._local.session = s
        return s

    def health(self) -> bool:
        try:
            r = self.s.get(self.base + "/models", timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def chat(self, model: str, prompt: str, *, temperature: float = 0.0,
             max_tokens: int = 1600, n: int = 1, retries: int = 3) -> list[str]:
        return [c for c, _ in self.chat_full(model, prompt, temperature=temperature,
                                             max_tokens=max_tokens, n=n, retries=retries)]

    def chat_full(self, model: str, prompt: str, *, temperature: float = 0.0,
                  max_tokens: int = 1600, n: int = 1, retries: int = 3
                  ) -> list[tuple[str, str | None]]:
        """Return (content, finish_reason) per choice.

        `finish_reason == "length"` means the answer was cut by `max_tokens`,
        not that the model produced no JSON: the distinction decides whether a
        document is missing at random or is a systematic casualty of its own
        length (DEVIATIONS D-28/D-30). The caller records it.
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "n": n,
        }
        last = None
        for attempt in range(retries):
            try:
                r = self.s.post(self.base + "/chat/completions", json=payload,
                                headers={"Authorization": f"Bearer {self.key}"},
                                timeout=self.timeout)
                if r.status_code >= 500:
                    raise RuntimeError(f"server {r.status_code}")
                r.raise_for_status()
                data = r.json()
                return [(c["message"]["content"], c.get("finish_reason"))
                        for c in data.get("choices", [])]
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 ** attempt)
        raise LLMUnavailable(f"chat failed after {retries}: {last}")


def parse_json(text: str) -> dict | None:
    """Best-effort JSON extraction from an LLM response."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    frag = t[start:end + 1]
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        frag = frag.replace("“", '"').replace("”", '"').replace("'", '"')
        frag = re.sub(r",\s*([}\]])", r"\1", frag)
        try:
            return json.loads(frag)
        except json.JSONDecodeError:
            return None
