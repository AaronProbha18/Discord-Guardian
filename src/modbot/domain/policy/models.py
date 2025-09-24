"""Policy domain models"""
from __future__ import annotations

from typing import List, Optional, Tuple, Dict, Union
import re
from pydantic import BaseModel, Field, field_validator, model_validator

_COND_RE = re.compile(
    r"^(?:"  # start
    r"toxicity\s*>=\s*(?P<gtoe>0(?:\.\d+)?|1(?:\.0+)?)"  # pattern 1
    r"|(?P<min>0(?:\.\d+)?|1(?:\.0+)?)\s*<=\s*toxicity\s*<\s*(?P<max>0(?:\.\d+)?|1(?:\.0+)?)"  # pattern 2
    r")$"
)


class ModerationRule(BaseModel):
    """Single toxicity-range rule mapping to a list of action strings."""
    name: str
    if_: str = Field(alias="if")
    actions: List[str]
    # Derived fields
    min_inclusive: float = 0.0
    max_exclusive: Optional[float] = None

    @field_validator("if_", mode="before")
    def validate_condition(cls, v: str):  # type: ignore[override]
        v = str(v).strip()
        m = _COND_RE.match(v)
        if not m:
            raise ValueError(
                "Condition must be of form 'toxicity >= X' or 'A <= toxicity < B' with 0-1 floats"
            )
        return v

    @model_validator(mode="after")
    def derive_ranges(self):  # type: ignore[override]
        cond = getattr(self, "if_", "")
        m = _COND_RE.match(cond)
        if not m:
            return self
        if m.group("gtoe"):
            self.min_inclusive = float(m.group("gtoe"))
            self.max_exclusive = None
        else:
            low = float(m.group("min"))
            high = float(m.group("max"))
            if not (0.0 <= low < high <= 1.0):
                raise ValueError("Invalid toxicity bounds")
            self.min_inclusive = low
            self.max_exclusive = high
        return self

    def matches(self, toxicity: float) -> bool:
        if toxicity < self.min_inclusive:
            return False
        if self.max_exclusive is not None and toxicity >= self.max_exclusive:
            return False
        return True


class EscalationPolicy(BaseModel):
    """Windowed threshold mapping base actions to follow-up actions."""
    window_minutes: int
    thresholds: Dict[str, Union[str, List[str]]]
    parsed: Dict[str, List[Tuple[int, str]]] = Field(default_factory=dict)

    @staticmethod
    def _key_to_base_action(key: str) -> Optional[str]:
        k = key.lower().strip()
        mapping = {
            "warns": "warn_user",
            "warnings": "warn_user",
            "timeouts": "timeout_member",
        }
        return mapping.get(k)

    @model_validator(mode="before")
    def parse_thresholds(cls, values):  # type: ignore[override]
        raw: Dict[str, Union[str, List[str]]] = values.get("thresholds", {}) or {}
        parsed: Dict[str, List[Tuple[int, str]]] = {}
        pat = re.compile(r"^(\d+)\s*->\s*(.+)$")
        for key, expr in raw.items():
            base = cls._key_to_base_action(key)
            if not base:
                continue
            if isinstance(expr, (list, tuple)):
                expr_list = [str(e).strip() for e in expr if str(e).strip()]
            else:
                import re as _re
                if ";" in str(expr) or "," in str(expr):
                    expr_list = [seg.strip() for seg in _re.split(r"[;,]", str(expr)) if seg.strip()]
                else:
                    expr_list = [str(expr).strip()]
            for single in expr_list:
                m = pat.match(single)
                if not m:
                    continue
                count = int(m.group(1))
                follow = m.group(2).strip()
                parsed.setdefault(base, []).append((count, follow))
        for base in parsed:
            parsed[base].sort(key=lambda x: x[0])
        values["parsed"] = parsed
        return values


class AppealsPolicy(BaseModel):
    channel: str
    retention_days: int


class ModerationPolicy(BaseModel):
    rules: List[ModerationRule]
    escalation: EscalationPolicy
    exempt_roles: List[str] = Field(default_factory=list)
    appeals: AppealsPolicy

    def evaluate_toxicity(self, toxicity: float) -> Tuple[Optional[ModerationRule], List[str]]:
        for rule in self.rules:
            if rule.matches(toxicity):
                return rule, rule.actions
        return None, []


__all__ = [
    'ModerationRule', 'EscalationPolicy', 'AppealsPolicy', 'ModerationPolicy'
]
