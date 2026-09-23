"""
Benchmark Runner — Phase 8
Runs all 20 benchmark cases end-to-end through the LangGraph fraud investigation agent.
Generates structured answer files in the benchmark/outputs directory.
Tracks confidence progression, actions taken, approval gates, and SAR filings.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import run_investigation

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 20 Benchmark Case specifications (cases from final two months)
BENCHMARK_CASES = [
    {"case_id": "CASE-BENCH-001", "client_id": "CLI-84920", "trigger_type": "signal", "description": "High velocity card-not-present burst from foreign IP"},
    {"case_id": "CASE-BENCH-002", "client_id": "CLI-11409", "trigger_type": "signal", "description": "Multiple failed attempts followed by high value transfer"},
    {"case_id": "CASE-BENCH-003", "client_id": "CLI-55912", "trigger_type": "report", "description": "Client dispute on recurring subscription charge"},
    {"case_id": "CASE-BENCH-004", "client_id": "CLI-99231", "trigger_type": "signal", "description": "New device associated with multiple existing accounts"},
    {"case_id": "CASE-BENCH-005", "client_id": "CLI-70144", "trigger_type": "analyst", "description": "Synthetic identity suspected on synthetic SSN cluster"},
    {"case_id": "CASE-BENCH-006", "client_id": "CLI-33019", "trigger_type": "signal", "description": "Rapid succession of small $1 authorization attempts"},
    {"case_id": "CASE-BENCH-007", "client_id": "CLI-66481", "trigger_type": "signal", "description": "Cross-border transaction on dormant account"},
    {"case_id": "CASE-BENCH-008", "client_id": "CLI-22904", "trigger_type": "report", "description": "Customer claims card was skimmed at gas station"},
    {"case_id": "CASE-BENCH-009", "client_id": "CLI-88123", "trigger_type": "signal", "description": "Shared email address linking 5 high-charge accounts"},
    {"case_id": "CASE-BENCH-010", "client_id": "CLI-44021", "trigger_type": "signal", "description": "Sudden deviation in behavioral spending category"},
    {"case_id": "CASE-BENCH-011", "client_id": "CLI-95102", "trigger_type": "analyst", "description": "Merchant referral for coordinated refund scam"},
    {"case_id": "CASE-BENCH-012", "client_id": "CLI-12890", "trigger_type": "signal", "description": "Card testing sequence on newly opened online merchant"},
    {"case_id": "CASE-BENCH-013", "client_id": "CLI-73349", "trigger_type": "signal", "description": "Tor exit node used for password reset and wire request"},
    {"case_id": "CASE-BENCH-014", "client_id": "CLI-51208", "trigger_type": "report", "description": "Friendly fraud allegation regarding gaming purchases"},
    {"case_id": "CASE-BENCH-015", "client_id": "CLI-60032", "trigger_type": "signal", "description": "Burst transactions with mismatched billing ZIP"},
    {"case_id": "CASE-BENCH-016", "client_id": "CLI-82194", "trigger_type": "signal", "description": "Emulator device footprint detected on checkout"},
    {"case_id": "CASE-BENCH-017", "client_id": "CLI-39045", "trigger_type": "analyst", "description": "Ring connectivity alert: shared proxy across 4 entities"},
    {"case_id": "CASE-BENCH-018", "client_id": "CLI-77412", "trigger_type": "signal", "description": "Simultaneous logins from two geographically distant IPs"},
    {"case_id": "CASE-BENCH-019", "client_id": "CLI-19830", "trigger_type": "signal", "description": "Repeated card declines followed by successful crypto buy"},
    {"case_id": "CASE-BENCH-020", "client_id": "CLI-94451", "trigger_type": "signal", "description": "BIN attack indicator on sequential card number ranges"}
]


def run_single_benchmark_case(case_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a single case through the investigation graph and saves results."""
    case_id = case_spec["case_id"]
    client_id = case_spec["client_id"]
    trigger_type = case_spec.get("trigger_type", "signal")
    desc = case_spec.get("description", "")

    trigger_data = {
        "case_id": case_id,
        "client_id": client_id,
        "description": desc,
        "amount": 1850.0,
        "merchant": "Online Retailer",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    t0 = time.time()
    try:
        final_state = run_investigation(trigger_data, trigger_type=trigger_type)
        duration = round(time.time() - t0, 3)

        answer_file = final_state.get("answer_file") or {}
        # Ensure base fields
        answer_file["case_id"] = case_id
        answer_file["client_id"] = client_id
        answer_file["duration_sec"] = duration
        answer_file["stop_reason"] = final_state.get("stop_reason")
        answer_file["evidence_loop_count"] = final_state.get("evidence_loop_count", 0)

        # Write case output file
        out_path = OUTPUT_DIR / f"{case_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(answer_file, f, indent=2)

        return {
            "case_id": case_id,
            "status": "SUCCESS",
            "leading_typology": answer_file.get("leading_typology"),
            "confidence": answer_file.get("confidence"),
            "actions_count": len(answer_file.get("actions_taken", [])),
            "sar_filed": any(a.get("action_type") == "file_sar" for a in answer_file.get("actions_taken", [])),
            "stop_reason": answer_file.get("stop_reason"),
            "loops": answer_file.get("evidence_loop_count"),
            "duration_sec": duration
        }
    except Exception as e:
        return {
            "case_id": case_id,
            "status": "ERROR",
            "error": str(e),
            "duration_sec": round(time.time() - t0, 3)
        }


def run_all_benchmarks(cases: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Runs all benchmark cases and produces a summary report."""
    if cases is None:
        cases = BENCHMARK_CASES

    print(f"=== Starting Benchmark Run: {len(cases)} Cases ===")
    results = []

    for i, case_spec in enumerate(cases, 1):
        print(f"[{i:02d}/{len(cases):02d}] Running {case_spec['case_id']} ({case_spec['client_id']})...", end=" ", flush=True)
        res = run_single_benchmark_case(case_spec)
        results.append(res)
        print(f"DONE in {res['duration_sec']}s -> {res.get('leading_typology', 'N/A')} ({res.get('confidence', 0):.2f})")

    # Generate summary stats
    successful = [r for r in results if r.get("status") == "SUCCESS"]
    sar_count = sum(1 for r in successful if r.get("sar_filed"))
    avg_duration = sum(r.get("duration_sec", 0) for r in results) / max(len(results), 1)

    typology_dist = {}
    for r in successful:
        t = r.get("leading_typology", "unknown")
        typology_dist[t] = typology_dist.get(t, 0) + 1

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": len(cases),
        "successful_cases": len(successful),
        "failed_cases": len(results) - len(successful),
        "avg_duration_sec": round(avg_duration, 2),
        "sar_filings_count": sar_count,
        "typology_distribution": typology_dist,
        "case_results": results
    }

    summary_file = OUTPUT_DIR / "summary_report.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== Benchmark Summary ===")
    print(f"Total: {summary['total_cases']} | Succeeded: {summary['successful_cases']} | Failed: {summary['failed_cases']}")
    print(f"Average Duration: {summary['avg_duration_sec']}s")
    print(f"SAR Filings: {sar_count}")
    print("Typology Distribution:")
    for typ, count in typology_dist.items():
        print(f"  - {typ}: {count}")
    print(f"\nAll outputs saved to: {OUTPUT_DIR}")

    return summary


if __name__ == "__main__":
    run_all_benchmarks()
