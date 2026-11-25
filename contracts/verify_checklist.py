# -*- coding: utf-8 -*-
"""Check the published checklist structure without executing its items."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "acceptance-checklist-72.json"
COVERAGE = HERE / "requirements-coverage.json"

# R9 is a global constraint over the complete set of checklist IDs.
EXPECTED_COVERAGE = {
    "R1": ["C01", "C02", "M01", "M02"],
    "R2": ["C01", "C07", "C12", "C13", "C14", "M01", "M07", "M12", "M13", "M14"],
    "R3": ["C07", "C08", "C15", "C16", "C17", "C18",
           "M07", "M08", "M15", "M16", "M17", "M18"],
    "R4": ["C02", "C19", "C20", "C21", "C22", "M02", "M19", "M20", "M21", "M22"],
    "R5": ["C13", "C14", "C20", "C22", "C23", "C24", "C25", "C26", "C27",
           "M13", "M14", "M20", "M22", "M23", "M24", "M25", "M26", "M27"],
    "R6": ["C23", "C26", "C27", "M23", "M26", "M27"],
    "R7": ["C28", "C29", "M28", "M29", "M34", "M38", "M39"],
    "R8": ["C11", "C29", "C30", "M11", "M29", "M30", "M33", "M34",
           "M35", "M36", "M37", "M38", "M39", "M40"],
    "R9": [f"C{n:02d}" for n in range(1, 33)] + [f"M{n:02d}" for n in range(1, 41)],
    "R10": ["C09", "C10", "C11", "M09", "M10", "M11", "M33", "M36"],
    "R11": ["C28", "C31", "C32", "M28", "M31", "M32"],
    "R12": ["C32", "M32"],
    "R13": ["C03", "C04", "C05", "C06", "C07", "C08",
            "M03", "M04", "M05", "M06", "M07", "M08"],
}

EXPECTED_IDS = [f"C{n:02d}" for n in range(1, 33)] + [f"M{n:02d}" for n in range(1, 41)]
C_REF = re.compile(r"\bC(0[1-9]|[12]\d|3[0-2])\b")
ITEM_FIELDS = {
    "id", "mode", "origin", "requirement_ids", "scenario", "expected", "status",
    "execution_mode", "run_id", "input_manifest_sha256", "consumer_evidence_refs", "reviewer",
}


def verify(contract, coverage):
    problems = []
    if not isinstance(contract, dict) or not isinstance(coverage, dict):
        return ["Both contract documents must be JSON objects"]
    items = contract.get("items")
    if not isinstance(items, list):
        problems.append("Checklist must contain an items array")
        items = []
    if len(items) != 72:
        problems.append(f"Expected 72 items, found {len(items)}")
    if (contract.get("concept_count"), contract.get("manufacturing_count"), contract.get("total"),
            contract.get("executed"), contract.get("state")) != (32, 40, 72, 0, "NOT_EXECUTED"):
        problems.append("Checklist must report 32 concept items, 40 manufacturing items and 0 executed")
    if contract.get("global_requirement_ids") != ["R9", "R12"]:
        problems.append("Global requirements differ from the contract")

    if any(not isinstance(item, dict) or ITEM_FIELDS != item.keys()
           or not isinstance(item["id"], str) for item in items):
        return [*problems, "Checklist item structure is invalid"]
    ids = [it.get("id") for it in items]
    missing = [i for i in EXPECTED_IDS if i not in ids]
    extra = [i for i in ids if i not in EXPECTED_IDS]
    dupes = sorted({i for i in ids if i and ids.count(i) > 1})
    if missing:
        problems.append(f"Missing IDs: {missing}")
    if extra:
        problems.append(f"Unexpected IDs: {extra}")
    if dupes:
        problems.append(f"Duplicate IDs: {dupes}")

    not_run = [it.get("id") for it in items if it.get("status") != "NOT_RUN"]
    if not_run:
        problems.append(f"Items with status other than NOT_RUN: {not_run}")

    for it in items:
        item_id = it["id"]
        expected_mode = "concept" if item_id.startswith("C") else "manufacturing"
        if it["mode"] != expected_mode or not all(
                isinstance(it[key], str) and it[key].strip()
                for key in ("origin", "scenario", "expected")):
            problems.append(f"{item_id} has invalid mode or descriptions")
        reqs = it["requirement_ids"]
        expected = {req for req, covered in EXPECTED_COVERAGE.items()
                    if req != "R9" and item_id in covered}
        if (not isinstance(reqs, list) or not all(isinstance(req, str) for req in reqs)
                or set(reqs) != expected or len(reqs) != len(expected)):
            problems.append(f"{item_id} requirement references are inconsistent")
        refs = it["consumer_evidence_refs"]
        if not isinstance(refs, list):
            problems.append(f"{item_id} must declare an evidence reference array")
        elif expected_mode == "manufacturing" and any(C_REF.search(str(ref)) for ref in refs):
            problems.append(f"{item_id} references concept acceptance evidence")

    got = coverage.get("coverage")
    if not isinstance(got, dict):
        problems.append("Coverage map must contain a coverage object")
        got = {}
    if list(got) != [f"R{n}" for n in range(1, 14)]:
        problems.append("Coverage map must declare R1–R13 in order")
    for req, expect in EXPECTED_COVERAGE.items():
        if got.get(req) != expect:
            problems.append(f"{req} checklist membership is inconsistent")

    if coverage.get("statistics") != {"total": 72, "NOT_RUN": 72, "PASS": 0}:
        problems.append("Coverage totals must report 72 items, 72 NOT_RUN and 0 PASS")
    return problems


def main() -> int:
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"FAIL Could not read the contract documents: {exc}", file=sys.stderr)
        return 1
    problems = verify(contract, coverage)
    if problems:
        print(f"FAIL {len(problems)} structure errors")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("PASS")
    print("Structure verified: 72 unique items, C01–C32 and M01–M40, covering R1–R13.")
    print("Acceptance execution: 72 NOT_RUN, 0 PASS. No manufacturing item uses concept evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
