from __future__ import annotations

from typing import Optional, List, Dict
import httpx
from ...logging import structured_logging as _log  # placeholder if moved later


class PerspectiveScorer:
    def __init__(self, api_key: str, attributes: Optional[List[str]] = None, timeout: int = 10):
        self.api_key = api_key
        self.attributes = attributes or ["TOXICITY"]
        self.timeout = timeout
        self.endpoint = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

    async def score(self, text: str) -> float:  # type: ignore[override]
        req = {
            "comment": {"text": text},
            "languages": ["en"],
            "requestedAttributes": {attr: {} for attr in self.attributes},
            "doNotStore": True,
        }
        params = {"key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(self.endpoint, params=params, json=req)
                r.raise_for_status()
                data = r.json()
        except Exception:
            return 0.0
        try:
            scores: Dict[str, float] = {}
            for attr in self.attributes:
                val = data["attributeScores"][attr]["summaryScore"]["value"]
                scores[attr] = float(val)
            if "TOXICITY" in scores:
                return float(scores["TOXICITY"])
            if scores:
                return max(scores.values())
        except Exception:
            pass
        return 0.0

__all__ = ['PerspectiveScorer']
