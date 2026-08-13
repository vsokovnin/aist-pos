#!/usr/bin/env python3
"""Вписать вердикты судей в findings.json.

Читает результат Workflow судей и обновляет findings.json.
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import fail

if os.environ.get("AUDIT_ROOT"):
    ROOT = Path(os.environ["AUDIT_ROOT"])
else:
    ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    parser = argparse.ArgumentParser(description="Вписать вердикты в findings.json")
    parser.add_argument("verdict_file", help="JSON-файл с вердиктами [{n, verdict, rationale}, ...]")
    args = parser.parse_args()

    findings_path = ROOT / "derivation" / "findings.json"
    if not findings_path.exists():
        fail(f"findings.json не найден: {findings_path}")

    verdict_path = Path(args.verdict_file)
    if not verdict_path.exists():
        fail(f"файл вердиктов не найден: {verdict_path}")

    # Прочитать findings
    try:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"findings.json невалидный JSON: {e}")

    # Прочитать вердикты
    try:
        verdicts = json.loads(verdict_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"файл вердиктов невалидный JSON: {e}")

    if not isinstance(verdicts, list):
        fail("файл вердиктов должен быть массивом [{n, verdict, rationale}, ...]")

    # Построить индекс находок по n
    finding_by_n = {f["n"]: f for f in findings}

    # Вписать вердикты
    applied = 0
    for v in verdicts:
        n = v.get("n")
        if n is None:
            fail(f"вердикт без поля n: {json.dumps(v)}")

        if n not in finding_by_n:
            fail(f"вердикт с n={n}, которого нет в findings")

        finding = finding_by_n[n]
        if finding.get("verdict") is not None:
            fail(f"находка n={n} уже имеет verdict={finding['verdict']}, не перезаписываю")

        verdict = v.get("verdict")
        rationale = v.get("rationale", "")

        if verdict not in ("CONFIRMED", "REJECTED"):
            fail(f"неверный verdict={verdict} для n={n}")

        if len(rationale) < 60:
            fail(f"rationale для n={n} короче 60 символов ({len(rationale)})")

        finding["verdict"] = verdict
        finding["rationale"] = rationale
        applied += 1

    # Записать findings
    findings_path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    # Подсчитать распределение
    by_cls = Counter(f.get("cls") for f in findings if f.get("verdict") is not None)
    by_verdict = Counter(f.get("verdict") for f in findings if f.get("verdict") is not None)

    print(f"✓ Вписано вердиктов: {applied}")
    print(f"По классам (все отсуженные): {dict(by_cls)}")
    print(f"По вердиктам (все отсуженные): {dict(by_verdict)}")


if __name__ == "__main__":
    main()
