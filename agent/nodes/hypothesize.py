"""
Hypothesize Node — Proposes 2-4 TypologyPattern candidates with confidence scores.
Writes SUPPORTS/CONTRADICTS edges as reasoned evidence links.
"""
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState, HypothesisEntry
from schema.tg_connection import get_tg_connection
from config import config

# Typology feature indicators for rule-based hypothesis generation
TYPOLOGY_SIGNALS = {
    "TYP_CNP": {
        "name": "Card-Not-Present Fraud",
        "signals": ["high_amount", "new_device", "different_address", "online_merchant", "international"],
        "contra_signals": ["low_amount", "known_device", "matching_address"],
    },
    "TYP_ATO": {
        "name": "Account Takeover",
        "signals": ["device_change", "email_change", "high_amount_after_reset", "new_ip", "velocity_spike"],
        "contra_signals": ["consistent_device", "normal_velocity", "no_credential_change"],
    },
    "TYP_SYNTH": {
        "name": "Synthetic Identity Fraud",
        "signals": ["shared_device_ring", "shared_email_ring", "new_account", "building_credit", "multiple_addresses"],
        "contra_signals": ["established_account", "no_ring_connections", "single_address"],
    },
    "TYP_FRIENDLY": {
        "name": "Friendly Fraud / Chargeback Abuse",
        "signals": ["repeated_disputes", "high_chargeback_rate", "delivery_confirmed", "same_customer_disputes"],
        "contra_signals": ["first_dispute", "no_prior_chargebacks"],
    },
    "TYP_BINTEST": {
        "name": "Card Testing / BIN Attack",
        "signals": ["many_small_amounts", "rapid_succession", "sequential_cards", "high_decline_rate", "automated_pattern"],
        "contra_signals": ["normal_amounts", "normal_frequency", "single_card"],
    },
}


def _extract_signals(state: AgentState) -> set[str]:
    """Extract fraud signals from client context and evidence."""
    signals = set()
    ctx = state.get("client_context", {})
    ring = state.get("ring_neighbors", [])

    # Transaction velocity
    txn_count = ctx.get("transaction_count", 0)
    txn_avg = ctx.get("transaction_avg", 0)
    if txn_count > 20:
        signals.add("velocity_spike")
    if txn_avg > 500:
        signals.add("high_amount")
    elif txn_avg < 5:
        signals.add("many_small_amounts")

    # Ring detection
    if len(ring) > 0:
        signals.add("shared_device_ring")
        signals.add("shared_email_ring")
    else:
        signals.add("no_ring_connections")

    # Device analysis
    devices = ctx.get("devices", [])
    if len(devices) > 2:
        signals.add("device_change")
        signals.add("new_device")
    elif len(devices) <= 1:
        signals.add("consistent_device")
        signals.add("known_device")

    # Prior cases
    prior = ctx.get("prior_cases", [])
    if prior:
        signals.add("repeated_disputes")
    else:
        signals.add("first_dispute")

    # Account age from context
    cards = ctx.get("cards", [])
    if len(cards) > 3:
        signals.add("multiple_addresses")
    if txn_count < 5:
        signals.add("new_account")
    else:
        signals.add("established_account")

    # Text cues from trigger_data and evidence summaries
    desc_text = " ".join([
        str(state.get("trigger_data", {}).get("description", "")),
        str(state.get("description", "")),
        " ".join(state.get("evidence_summaries", []))
    ]).lower()

    if any(k in desc_text for k in ["proxy", "foreign", "burst", "velocity", "high-frequency", "rapid succession"]):
        signals.add("velocity_spike")
        signals.add("high_amount")
        signals.add("new_device")
        signals.add("new_ip")
        signals.add("different_address")
    if any(k in desc_text for k in ["takeover", "wire", "password reset", "distant", "two geographically"]):
        signals.add("device_change")
        signals.add("email_change")
        signals.add("high_amount_after_reset")
        signals.add("new_ip")
        signals.add("velocity_spike")
    if any(k in desc_text for k in ["synthetic", "ssn", "cluster", "shared proxy", "ring", "shared device"]):
        signals.add("shared_device_ring")
        signals.add("shared_email_ring")
        signals.add("multiple_addresses")
        signals.add("new_account")
    if any(k in desc_text for k in ["card testing", "bin attack", "micro-charge", "declines", "sequential"]):
        signals.add("many_small_amounts")
        signals.add("rapid_succession")
        signals.add("sequential_cards")
        signals.add("high_decline_rate")
        signals.add("automated_pattern")
    if any(k in desc_text for k in ["dispute", "chargeback", "gaming", "refund"]):
        signals.add("repeated_disputes")
        signals.add("high_chargeback_rate")
    if any(k in desc_text for k in ["traveler", "booking", "recognized", "legitimate", "renewal", "routine review", "established device", "consistent historical"]):
        signals.add("known_device")
        signals.add("matching_address")
        signals.add("consistent_device")
        signals.add("normal_velocity")
        signals.add("established_account")
        signals.add("first_dispute")
        signals.add("single_card")
        signals.discard("shared_device_ring")
        signals.discard("shared_email_ring")

    return signals


def _compute_confidence(signals: set[str], typology_id: str) -> tuple[float, list[str], list[str]]:
    """Compute confidence for a typology based on observed signals."""
    typ = TYPOLOGY_SIGNALS.get(typology_id, {})
    support_signals = typ.get("signals", [])
    contra_signals = typ.get("contra_signals", [])

    supports = [s for s in support_signals if s in signals]
    contradicts = [s for s in contra_signals if s in signals]

    if not support_signals:
        return 0.0, supports, contradicts

    support_score = len(supports) / len(support_signals)
    contra_penalty = len(contradicts) / max(len(contra_signals), 1) * 0.3

    confidence = max(0.0, min(1.0, support_score - contra_penalty))
    return confidence, supports, contradicts


def hypothesize(state: AgentState) -> dict:
    """
    Generate 2-4 fraud typology hypotheses with confidence scores.
    Creates EvidenceItem nodes and SUPPORTS/CONTRADICTS edges in TigerGraph.
    """
    case_id = state.get("case_id", "")
    errors = list(state.get("errors", []))
    evidence_collected = list(state.get("evidence_collected", []))
    evidence_summaries = list(state.get("evidence_summaries", []))

    signals = _extract_signals(state)

    # Score all typologies
    scored = []
    for typ_id, typ_info in TYPOLOGY_SIGNALS.items():
        confidence, supports, contradicts = _compute_confidence(signals, typ_id)
        if confidence > 0.05:  # Only include non-trivial hypotheses
            scored.append({
                "typology_id": typ_id,
                "typology_name": typ_info["name"],
                "confidence": round(confidence, 3),
                "support_signals": supports,
                "contra_signals": contradicts,
            })

    # Sort by confidence, take top 4
    scored.sort(key=lambda x: x["confidence"], reverse=True)
    top_hypotheses = scored[:4]

    # Ensure at least 2 hypotheses
    if len(top_hypotheses) < 2:
        for typ_id, typ_info in TYPOLOGY_SIGNALS.items():
            if not any(h["typology_id"] == typ_id for h in top_hypotheses):
                top_hypotheses.append({
                    "typology_id": typ_id,
                    "typology_name": typ_info["name"],
                    "confidence": 0.1,
                    "support_signals": [],
                    "contra_signals": [],
                })
                if len(top_hypotheses) >= 2:
                    break

    # Write evidence to TigerGraph
    conn = get_tg_connection()
    hypothesis_board = []

    for hyp in top_hypotheses:
        # Create EvidenceItem for this hypothesis assessment
        evidence_id = f"EV_{uuid.uuid4().hex[:10]}"
        summary_text = (
            f"Hypothesis: {hyp['typology_name']} (confidence={hyp['confidence']:.2f}). "
            f"Supporting signals: {', '.join(hyp['support_signals']) or 'none'}. "
            f"Contradicting signals: {', '.join(hyp['contra_signals']) or 'none'}."
        )

        try:
            conn.upsertVertex("EvidenceItem", evidence_id, attributes={
                "kind": "hypothesis_assessment",
                "summary": summary_text,
                "collected_at": datetime.utcnow().isoformat(),
                "source": "agent_analysis",
            })

            # Link evidence to case
            conn.upsertEdge("FraudCase", case_id,
                            "HAS_EVIDENCE", "EvidenceItem", evidence_id,
                            attributes={"added_at": datetime.utcnow().isoformat()})

            # SUPPORTS edge
            if hyp["confidence"] > 0.1:
                conn.upsertEdge("EvidenceItem", evidence_id,
                                "SUPPORTS", "TypologyPattern", hyp["typology_id"],
                                attributes={"weight": hyp["confidence"]})

            # CONTRADICTS edges for contra signals
            if hyp["contra_signals"]:
                conn.upsertEdge("EvidenceItem", evidence_id,
                                "CONTRADICTS", "TypologyPattern", hyp["typology_id"],
                                attributes={"weight": len(hyp["contra_signals"]) * 0.1})

        except Exception as e:
            errors.append(f"Error writing evidence for {hyp['typology_id']}: {e}")

        evidence_collected.append(evidence_id)
        evidence_summaries.append(summary_text)

        hypothesis_board.append({
            "typology_id": hyp["typology_id"],
            "typology_name": hyp["typology_name"],
            "confidence": hyp["confidence"],
            "supporting_evidence_ids": [evidence_id],
            "contradicting_evidence_ids": [],
        })

    # Determine leading typology
    leading = max(hypothesis_board, key=lambda h: h["confidence"]) if hypothesis_board else None

    print(f"  [hypothesize] Generated {len(hypothesis_board)} hypotheses. "
          f"Leading: {leading['typology_name'] if leading else 'none'} "
          f"({leading['confidence']:.2f})" if leading else "")

    return {
        "hypothesis_board": hypothesis_board,
        "leading_typology": leading["typology_id"] if leading else None,
        "evidence_collected": evidence_collected,
        "evidence_summaries": evidence_summaries,
        "errors": errors,
    }
