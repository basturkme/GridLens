"""Input validation helpers used by the editor panel and numeric fields."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    value: float | None = None
    error: str = ""


def parse_float(
    text: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    allow_empty: bool = False,
) -> ValidationResult:
    text = text.strip()
    if not text:
        if allow_empty:
            return ValidationResult(ok=True, value=None)
        return ValidationResult(ok=False, error="Value required.")
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return ValidationResult(ok=False, error="Must be a number.")
    if minimum is not None and value < minimum:
        return ValidationResult(ok=False, error=f"Must be ≥ {minimum}.")
    if maximum is not None and value > maximum:
        return ValidationResult(ok=False, error=f"Must be ≤ {maximum}.")
    return ValidationResult(ok=True, value=value)
