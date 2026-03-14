"""SOP Loader — reads agents/sops.yaml and returns a merged config dict.

Usage::

    from legacylens.agents.sop_loader import load_sop

    sop = load_sop("cautious")   # returns dict of pipeline params
    result = generate_verified_explanation(..., sop=sop)

Falls back to empty dict (code defaults) if the YAML file is missing
or the requested variant doesn't exist — never raises.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Location of the SOP yaml relative to this file
_SOPS_FILE = Path(__file__).parent / "sops.yaml"

# Keys understood by generate_verified_explanation()
_VALID_KEYS = {
    "writer_temperature",
    "critic_temperature",
    "max_iterations",
    "repetition_variant",
    "run_finalizer",
    "run_regeneration",
}

# Hard-coded fallback so we don't need PyYAML at import time
_DEFAULTS: dict[str, Any] = {
    "writer_temperature": 0.3,
    "critic_temperature": 0.0,
    "max_iterations": 5,
    "repetition_variant": None,
    "run_finalizer": False,
    "run_regeneration": True,
}


def _parse_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML parser sufficient for our flat-key SOP format.

    Supports:
      - Top-level section headers (``key:``)
      - Nested ``  key: value`` pairs (string, int, float, bool, null)

    Does NOT support: lists, multi-line values, anchors.
    """
    result: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Skip comments and blank lines
        if not line or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if ":" not in stripped:
            continue

        key_part, _, val_part = stripped.partition(":")
        key = key_part.strip()
        val_raw = val_part.strip()

        # Strip inline comment
        if "#" in val_raw:
            val_raw = val_raw[: val_raw.index("#")].strip()

        if indent == 0:
            # Section header (e.g.  "default:")
            current_section = key
            result[current_section] = {}
        elif current_section is not None:
            # Nested key-value
            result[current_section][key] = _coerce(val_raw)

    return result


def _coerce(val: str) -> Any:
    """Coerce a raw YAML scalar string to a Python type."""
    if val in ("null", "~", ""):
        return None
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    # Strip surrounding quotes
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def load_sop(variant: str | None = None) -> dict[str, Any]:
    """Load an SOP variant and return a merged config dict.

    Args:
        variant: Name of the SOP variant (e.g. ``"cautious"``).
                 ``None`` or ``"default"`` returns the default SOP.

    Returns:
        Dict of pipeline parameters ready to be unpacked into
        ``generate_verified_explanation(**sop)``.
        Unknown keys are stripped; missing keys keep code defaults.
    """
    if not variant or variant == "default":
        return {}  # Use code defaults entirely

    try:
        raw = _SOPS_FILE.read_text(encoding="utf-8")
        parsed = _parse_yaml(raw)
    except (OSError, Exception):
        # YAML missing or unparseable — silently fall back
        return {}

    section = parsed.get(variant)
    if not section:
        return {}  # Unknown variant → use defaults

    # Merge: start from defaults, overlay section values, strip unknown keys
    merged = {k: v for k, v in section.items() if k in _VALID_KEYS}
    return merged


def list_variants() -> list[str]:
    """Return all variant names defined in sops.yaml."""
    try:
        raw = _SOPS_FILE.read_text(encoding="utf-8")
        parsed = _parse_yaml(raw)
        return list(parsed.keys())
    except Exception:
        return ["default"]
