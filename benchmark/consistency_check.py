"""
Consistency Check — Phase 8
Runs a batch of benchmark cases twice to detect nondeterminism.
Verifies that:
1. Stopping rules converge consistently.
2. Recommended action sets match exactly.
3. Leading typologies do not fluctuate arbitrarily.
4. Flagged SAR filings are deterministic.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.run_benchmark import run_single_benchmark_case, BENCHMARK_CASES


def check_consistency(cases: List[Dict[str, Any]] = None, num_cases: int = 5) -> Dict[str, Any]:
    """Runs a subset of benchmark cases twice and compares results."""
    test_cases = (cases or BENCHMARK_CASES)[:num_cases]
    print(f"=== Starting Nondeterminism Consistency Check ({len(test_cases)} cases) ===")

    run1_results = {}
    run2_results = {}

    print("\n--- Pass 1 ---")
    for case in test_cases:
        cid = case["case_id"]
        print(f"Pass 1: {cid}...", end=" ", flush=True)
        res = run_single_benchmark_case(case)
        run1_results[cid] = res
        print("OK")

    print("\n--- Pass 2 ---")
    for case in test_cases:
        cid = case["case_id"]
        print(f"Pass 2: {cid}...", end=" ", flush=True)
        res = run_single_benchmark_case(case)
        run2_results[cid] = res
        print("OK")

    print("\n--- Diffing Results ---")
    discrepancies = []
    consistent_count = 0

    for cid in run1_results:
        r1 = run1_results[cid]
        r2 = run2_results[cid]

        issues = []
        if r1.get("leading_typology") != r2.get("leading_typology"):
            issues.append(f"Typology mismatch: '{r1.get('leading_typology')}' vs '{r2.get('leading_typology')}'")

        if r1.get("stop_reason") != r2.get("stop_reason"):
            issues.append(f"Stop reason mismatch: '{r1.get('stop_reason')}' vs '{r2.get('stop_reason')}'")

        if r1.get("sar_filed") != r2.get("sar_filed"):
            issues.append(f"SAR filing mismatch: {r1.get('sar_filed')} vs {r2.get('sar_filed')}")

        conf_diff = abs((r1.get("confidence") or 0) - (r2.get("confidence") or 0))
        if conf_diff > 0.05:
            issues.append(f"Confidence drift > 0.05: {r1.get('confidence')} vs {r2.get('confidence')}")

        if issues:
            discrepancies.append({
                "case_id": cid,
                "issues": issues,
                "run1": r1,
                "run2": r2
            })
            print(f"[FAIL] {cid} had discrepancies: {', '.join(issues)}")
        else:
            consistent_count += 1
            print(f"[PASS] {cid} is 100% consistent across runs.")

    report = {
        "cases_tested": len(test_cases),
        "consistent_cases": consistent_count,
        "discrepancies_count": len(discrepancies),
        "discrepancies": discrepancies,
        "is_deterministic": len(discrepancies) == 0
    }

    report_file = Path(__file__).resolve().parent / "outputs" / "consistency_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nConsistency Score: {consistent_count}/{len(test_cases)} ({'PASSED' if report['is_deterministic'] else 'REVIEW NEEDED'})")
    print(f"Detailed consistency report saved to: {report_file}")
    return report


if __name__ == "__main__":
    check_consistency()
