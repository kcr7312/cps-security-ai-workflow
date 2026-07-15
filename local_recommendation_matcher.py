#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "cps_recommendation_catalog_v1_1.json"
RULES_PATH = BASE_DIR / "cps_recommendation_match_rules_v1_1.json"


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _norm_finding_name(value: Any, cfg: dict[str, Any]) -> str:
    text = unicodedata.normalize(cfg.get("unicode_form", "NFKC"), str(value or ""))
    if cfg.get("collapse_internal_whitespace", True):
        text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if cfg.get("remove_trailing_candidate_word", True):
        suffixes = cfg.get("trailing_candidate_words", ["후보"])
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                updated = re.sub(rf"(?:\s+|/)?{re.escape(str(suffix))}\s*$", "", text, flags=re.IGNORECASE).strip()
                if updated != text:
                    text = updated
                    changed = True
    return text.casefold() if cfg.get("case_insensitive_finding_name", True) else text


def _norm_protocol(value: Any, cfg: dict[str, Any]) -> str:
    text = unicodedata.normalize(cfg.get("unicode_form", "NFKC"), str(value or "")).strip().upper()
    aliases = {str(k).upper(): str(v).upper() for k, v in cfg.get("protocol_aliases", {}).items()}
    text = aliases.get(text, text)
    return text


def _norm_zone(value: Any) -> str:
    return str(value or "").strip().upper()


def _norm_port(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_finding(finding: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    risk_tags = finding.get("risk_tags") or []
    if isinstance(risk_tags, str):
        risk_tags = [risk_tags]
    return {
        **finding,
        "finding_name": _norm_finding_name(finding.get("finding_name"), cfg),
        "protocol": _norm_protocol(finding.get("protocol"), cfg),
        "source_zone": _norm_zone(finding.get("source_zone")),
        "destination_zone": _norm_zone(finding.get("destination_zone")),
        "source_port": _norm_port(finding.get("source_port")),
        "destination_port": _norm_port(finding.get("destination_port")),
        "session_state": _norm_zone(finding.get("session_state")),
        "risk_tags": {_norm_zone(v) for v in risk_tags if str(v).strip()},
    }


def _values_normalized(key: str, values: list[Any], cfg: dict[str, Any]) -> list[Any]:
    if key == "finding_name_in":
        return [_norm_finding_name(v, cfg) for v in values]
    if key == "protocol_in":
        return [_norm_protocol(v, cfg) for v in values]
    if key in {"source_zone_in", "destination_zone_in", "session_state_in", "risk_tags_any"}:
        return [_norm_zone(v) for v in values]
    if key in {"source_port_in", "destination_port_in"}:
        return [_norm_port(v) for v in values]
    return values


def condition_matches(condition: dict[str, Any], finding: dict[str, Any], cfg: dict[str, Any]) -> bool:
    if "all" in condition:
        return all(condition_matches(item, finding, cfg) for item in condition["all"])
    if "any" in condition:
        return any(condition_matches(item, finding, cfg) for item in condition["any"])

    results: list[bool] = []
    for key, values in condition.items():
        values = values if isinstance(values, list) else [values]
        normalized = _values_normalized(key, values, cfg)
        if key == "finding_name_in":
            results.append(finding.get("finding_name") in normalized)
        elif key == "protocol_in":
            results.append(finding.get("protocol") in normalized)
        elif key == "destination_port_in":
            results.append(finding.get("destination_port") in normalized)
        elif key == "source_port_in":
            results.append(finding.get("source_port") in normalized)
        elif key == "source_zone_in":
            results.append(finding.get("source_zone") in normalized)
        elif key == "destination_zone_in":
            results.append(finding.get("destination_zone") in normalized)
        elif key == "session_state_in":
            results.append(finding.get("session_state") in normalized)
        elif key == "risk_tags_any":
            results.append(bool(finding.get("risk_tags", set()).intersection(normalized)))
        else:
            raise ValueError(f"Unsupported rule operator: {key}")
    return all(results) if results else False


def load_runtime() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
        json.loads(RULES_PATH.read_text(encoding="utf-8")),
    )


def match_finding(finding: dict[str, Any], catalog: dict[str, Any] | None = None, rules_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    if catalog is None or rules_doc is None:
        catalog, rules_doc = load_runtime()
    cfg = rules_doc.get("normalization", {})
    normalized = normalize_finding(finding, cfg)
    rules = sorted(
        (r for r in rules_doc.get("rules", []) if r.get("enabled", True)),
        key=lambda r: int(r.get("priority", 0)),
        reverse=True,
    )
    for rule in rules:
        if condition_matches(rule.get("when", {}), normalized, cfg):
            rid = rule["recommendation_id"]
            rec = catalog["recommendations"][rid]
            return {
                "match_status": "matched",
                "manual_review_required": False,
                "rule_id": rule["rule_id"],
                "priority": rule["priority"],
                "recommendation_id": rid,
                "report": rec["report"],
            }
    return dict(rules_doc["fallback"])


if __name__ == "__main__":
    import sys
    payload = json.load(sys.stdin)
    print(json.dumps(match_finding(payload), ensure_ascii=False, indent=2))
