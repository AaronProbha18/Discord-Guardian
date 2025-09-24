from __future__ import annotations


class NeutralScorer:
    async def score(self, text: str) -> float:  # type: ignore[override]
        return 0.0

__all__ = ['NeutralScorer']
