from backend.app.llm_analyzer import analyze_with_llm
from backend.app.kubernetes_analyzer import analyze_kubernetes_evidence

from dataclasses import asdict, is_dataclass


def _to_llm_evidence(evidence) -> dict:
    """
    Convert evidence objects into a JSON-safe dictionary
    suitable for LLM analysis.
    """

    if evidence is None:
        return {}

    if is_dataclass(evidence):
        return asdict(evidence)

    if isinstance(evidence, dict):
        return evidence

    return {
        "evidence": str(evidence),
    }

def analyze_hybrid(
    evidence: dict,
    ml_result: dict | None = None,
    kubernetes_evidence=None,
) -> dict:
    """
    Combine structured ML analysis, LLM contextual reasoning,
    and explicit Kubernetes evidence.

    The ML model provides learned classification.
    The LLM provides contextual reasoning.
    The Kubernetes analyzer provides structured,
    source-specific operational evidence.

    No single source blindly overrides another.
    Conflicts are surfaced for human review.
    """

    ml_result = ml_result or {}

    llm_evidence = _to_llm_evidence(evidence)

    # ---------------------------------------------------------
    # 1. Run LLM analysis
    # ---------------------------------------------------------

    
    llm_result = analyze_with_llm(
    evidence=llm_evidence,
    ml_result=ml_result,
    )

    # ---------------------------------------------------------
    # 2. Analyze Kubernetes evidence
    # ---------------------------------------------------------

    kubernetes_result = analyze_kubernetes_evidence(
        kubernetes_evidence
    )

    # ---------------------------------------------------------
    # 3. Extract classifications
    # ---------------------------------------------------------

    ml_class = ml_result.get(
        "incident_class",
        "Unknown",
    )

    ml_confidence = ml_result.get(
        "confidence"
    )

    llm_class = llm_result.get(
        "incident_class",
        "Unknown",
    )

    llm_confidence = llm_result.get(
        "confidence"
    )

    kubernetes_class = kubernetes_result.get(
        "incident_class",
        "Unknown",
    )

    kubernetes_confidence = kubernetes_result.get(
        "confidence"
    )

    ml_available = (
        ml_result.get("status") == "success"
        and ml_class != "Unknown"
    )

    llm_available = (
        llm_result.get("status") == "success"
        and llm_class != "Unknown"
    )

    kubernetes_available = (
        kubernetes_result.get("status") == "success"
        and kubernetes_class != "Unknown"
    )

    # ---------------------------------------------------------
    # 4. Kubernetes evidence + ML + LLM agreement
    # ---------------------------------------------------------

    if (
        kubernetes_available
        and ml_available
        and llm_available
    ):

        if (
            ml_class == kubernetes_class
            and llm_class == kubernetes_class
        ):

            confidence_values = [
                value
                for value in (
                    ml_confidence,
                    llm_confidence,
                    kubernetes_confidence,
                )
                if value is not None
            ]

            if confidence_values:
                final_confidence = (
                    sum(confidence_values)
                    / len(confidence_values)
                )
            else:
                final_confidence = None

            return {
                "final_class": kubernetes_class,
                "final_confidence": final_confidence,
                "decision_mode": "ML_LLM_K8S_AGREEMENT",
                "ml": ml_result,
                "llm": llm_result,
                "kubernetes": kubernetes_result,
                "agreement": True,
                "human_review": False,
            }

        # -----------------------------------------------------
        # Kubernetes evidence conflicts with ML or LLM
        # -----------------------------------------------------

        return {
            "final_class": kubernetes_class,
            "final_confidence": kubernetes_confidence,
            "decision_mode": "K8S_MODEL_CONFLICT",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 5. Kubernetes + LLM agreement
    # ---------------------------------------------------------

    if kubernetes_available and llm_available:

        if kubernetes_class == llm_class:

            confidence_values = [
                value
                for value in (
                    kubernetes_confidence,
                    llm_confidence,
                )
                if value is not None
            ]

            if confidence_values:
                final_confidence = (
                    sum(confidence_values)
                    / len(confidence_values)
                )
            else:
                final_confidence = None

            return {
                "final_class": kubernetes_class,
                "final_confidence": final_confidence,
                "decision_mode": "K8S_LLM_AGREEMENT",
                "ml": ml_result,
                "llm": llm_result,
                "kubernetes": kubernetes_result,
                "agreement": True,
                "human_review": False,
            }

        return {
            "final_class": kubernetes_class,
            "final_confidence": kubernetes_confidence,
            "decision_mode": "K8S_LLM_CONFLICT",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 6. Kubernetes + ML agreement
    # ---------------------------------------------------------

    if kubernetes_available and ml_available:

        if kubernetes_class == ml_class:

            confidence_values = [
                value
                for value in (
                    kubernetes_confidence,
                    ml_confidence,
                )
                if value is not None
            ]

            if confidence_values:
                final_confidence = (
                    sum(confidence_values)
                    / len(confidence_values)
                )
            else:
                final_confidence = None

            return {
                "final_class": kubernetes_class,
                "final_confidence": final_confidence,
                "decision_mode": "ML_K8S_AGREEMENT",
                "ml": ml_result,
                "llm": llm_result,
                "kubernetes": kubernetes_result,
                "agreement": True,
                "human_review": False,
            }

        return {
            "final_class": kubernetes_class,
            "final_confidence": kubernetes_confidence,
            "decision_mode": "K8S_ML_CONFLICT",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 7. Kubernetes evidence only
    # ---------------------------------------------------------

    if kubernetes_available:

        return {
            "final_class": kubernetes_class,
            "final_confidence": kubernetes_confidence,
            "decision_mode": "K8S_EVIDENCE_ONLY",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 8. Existing ML + LLM logic
    # ---------------------------------------------------------

    if llm_result["status"] != "success":

        if ml_available:
            return {
                "final_class": ml_class,
                "final_confidence": ml_confidence,
                "decision_mode": "ML_ONLY_LLM_UNAVAILABLE",
                "ml": ml_result,
                "llm": llm_result,
                "kubernetes": kubernetes_result,
                "agreement": False,
                "human_review": True,
            }

        return {
            "final_class": "Unknown",
            "final_confidence": None,
            "decision_mode": "INSUFFICIENT_EVIDENCE",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }
    
    if ml_available and llm_available:

        if ml_class == llm_class:

            confidence_values = [
                value
                for value in (
                    ml_confidence,
                    llm_confidence,
                )
                if value is not None
            ]

            if confidence_values:
                final_confidence = (
                    sum(confidence_values)
                    / len(confidence_values)
                )
            else:
                final_confidence = None

            return {
                "final_class": ml_class,
                "final_confidence": final_confidence,
                "decision_mode": "ML_LLM_AGREEMENT",
                "ml": ml_result,
                "llm": llm_result,
                "kubernetes": kubernetes_result,
                "agreement": True,
                "human_review": False,
            }
        
        return {
            "final_class": llm_class,
            "final_confidence": llm_confidence,
            "decision_mode": "ML_LLM_DISAGREEMENT",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }
    
    if not ml_available and llm_available:

        return {
            "final_class": llm_class,
            "final_confidence": llm_confidence,
            "decision_mode": "LLM_ONLY_ML_UNAVAILABLE",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }
    
    if ml_available and not llm_available:

        return {
            "final_class": ml_class,
            "final_confidence": ml_confidence,
            "decision_mode": "ML_ONLY_LLM_UNCERTAIN",
            "ml": ml_result,
            "llm": llm_result,
            "kubernetes": kubernetes_result,
            "agreement": False,
            "human_review": True,
        }
    
    return {
        "final_class": "Unknown",
        "final_confidence": None,
        "decision_mode": "INSUFFICIENT_EVIDENCE",
        "ml": ml_result,
        "llm": llm_result,
        "kubernetes": kubernetes_result,
        "agreement": False,
        "human_review": True,
    }