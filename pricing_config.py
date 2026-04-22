"""Single source of truth for plan prices: Stripe `unit_amount` (cents) + UI display string."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_PRICING_PATH = REPO_ROOT / "pricing.json"

REQUIRED_PLANS = ("signature_plan", "premium_plan")


def load_pricing(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load and validate ``pricing.json``."""
    p = path or DEFAULT_PRICING_PATH
    if not p.is_file():
        raise FileNotFoundError(f"Missing pricing file: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pricing.json must contain a top-level object.")
    out: dict[str, dict[str, Any]] = {}
    for key in REQUIRED_PLANS:
        row = raw.get(key)
        if not isinstance(row, dict):
            raise ValueError(f"pricing.json missing or invalid object for {key!r}.")
        display = row.get("display")
        product_name = row.get("product_name")
        amount = row.get("amount_cents")
        if not isinstance(display, str) or not display.strip():
            raise ValueError(f"pricing.json {key}.display must be a non-empty string.")
        if not isinstance(product_name, str) or not product_name.strip():
            raise ValueError(f"pricing.json {key}.product_name must be a non-empty string.")
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"pricing.json {key}.amount_cents must be a positive integer (USD cents).")
        out[key] = {
            "display": display.strip(),
            "product_name": product_name.strip(),
            "amount_cents": amount,
        }
    return out


def pricing_path() -> Path:
    return DEFAULT_PRICING_PATH
