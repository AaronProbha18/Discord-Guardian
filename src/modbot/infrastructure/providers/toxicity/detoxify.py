from __future__ import annotations

class DetoxifyScorer:
    def __init__(self, model: str = "original"):
        from detoxify import Detoxify  # type: ignore
        self.detox = Detoxify(model)

    async def score(self, text: str) -> float:  # type: ignore[override]
        import asyncio
        loop = asyncio.get_running_loop()

        def _run():
            preds = self.detox.predict(text)
            if "toxicity" in preds:
                return float(preds["toxicity"])
            return float(list(preds.values())[0])

        return await loop.run_in_executor(None, _run)

__all__ = ['DetoxifyScorer']
