#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CATALOG = BASE_DIR / "cps_recommendation_catalog_v1_1.json"
RULES = BASE_DIR / "cps_recommendation_match_rules_v1_1.json"
TESTS = BASE_DIR / "tests" / "matcher_cases_v1_1.json"

REPORT_FIELDS = [
    "title", "recommendation_direction", "action_purpose", "targets", "action_steps",
    "commands", "verification", "operational_cautions", "rollback_change_management",
]


def main() -> int:
    errors: list[str] = []
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rules_doc = json.loads(RULES.read_text(encoding="utf-8"))
    recommendations = catalog.get("recommendations", {})
    order = catalog.get("recommendation_order", [])

    if not isinstance(recommendations, dict):
        errors.append("catalog.recommendations must be an object keyed by recommendation_id")
    if set(order) != set(recommendations):
        errors.append("recommendation_order and recommendations keys differ")

    for rid, rec in recommendations.items():
        if rec.get("recommendation_id") != rid:
            errors.append(f"{rid}: embedded recommendation_id mismatch")
        report = rec.get("report", {})
        for field in REPORT_FIELDS:
            if field not in report:
                errors.append(f"{rid}: missing report.{field}")
        for field in REPORT_FIELDS[:3]:
            if not isinstance(report.get(field), str) or not report.get(field, "").strip():
                errors.append(f"{rid}: report.{field} must be a non-empty string")
        for field in REPORT_FIELDS[3:]:
            if not isinstance(report.get(field), list) or not report.get(field):
                errors.append(f"{rid}: report.{field} must be a non-empty list")
        for i, command in enumerate(report.get("commands", [])):
            if not isinstance(command, dict) or not {"label", "language", "content"}.issubset(command):
                errors.append(f"{rid}: invalid commands[{i}]")

    rule_ids = [r.get("rule_id") for r in rules_doc.get("rules", [])]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append(f"duplicate rule_id: {[x for x,c in Counter(rule_ids).items() if c > 1]}")
    priorities = [int(r.get("priority", 0)) for r in rules_doc.get("rules", [])]
    if priorities != sorted(priorities, reverse=True):
        errors.append("rules are not stored in descending priority order")

    reachable = {r.get("recommendation_id") for r in rules_doc.get("rules", []) if r.get("enabled", True)}
    dangling = reachable - set(recommendations)
    unreachable = set(recommendations) - reachable
    if dangling:
        errors.append(f"dangling recommendation IDs in rules: {sorted(dangling)}")
    if unreachable:
        errors.append(f"unreachable recommendations: {sorted(unreachable)}")

    sys.path.insert(0, str(BASE_DIR))
    from local_recommendation_matcher import match_finding
    tests = json.loads(TESTS.read_text(encoding="utf-8"))
    for case in tests:
        actual = match_finding(case["finding"], catalog, rules_doc).get("recommendation_id")
        if actual != case["expected"]:
            errors.append(f"test {case['name']}: expected {case['expected']}, got {actual}")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDATION PASSED")
    print(f"- recommendations: {len(recommendations)}")
    print(f"- enabled rules: {len(reachable)} recommendation IDs / {len(rules_doc['rules'])} rules")
    print(f"- tests: {len(tests)}")
    print("- unreachable recommendations: 0")
    print("- dangling recommendation IDs: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
