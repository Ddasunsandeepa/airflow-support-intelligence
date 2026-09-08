from backend.app.llm_analyzer import analyze_with_llm


def analyze_hybrid(
    evidence: dict,
    ml_result: dict | None = None,
) -> dict:
    """
    Combine structured ML analysis with LLM-based
    contextual reasoning.

    The LLM complements the ML model rather than
    replacing it.
    """

    ml_result = ml_result or {}

    # ---------------------------------------------------------
    # 1. Run LLM analysis
    # ---------------------------------------------------------

    llm_result = analyze_with_llm(
        evidence=evidence,
        ml_result=ml_result,
    )

    # ---------------------------------------------------------
    # 2. Extract classifications
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

    ml_available = (
        ml_result.get("status") == "success"
        and ml_class != "Unknown"
    )

    llm_available = (
        llm_result.get("status") == "success"
        and llm_class != "Unknown"
    )

    # ---------------------------------------------------------
    # 3. Handle unavailable LLM
    # ---------------------------------------------------------

    if llm_result["status"] != "success":

        if ml_available:
            return {
                "final_class": ml_class,
                "final_confidence": ml_confidence,
                "decision_mode": "ML_ONLY_LLM_UNAVAILABLE",
                "ml": ml_result,
                "llm": llm_result,
                "agreement": False,
                "human_review": True,
            }

        return {
            "final_class": "Unknown",
            "final_confidence": None,
            "decision_mode": "INSUFFICIENT_EVIDENCE",
            "ml": ml_result,
            "llm": llm_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 4. Both ML and LLM produced a classification
    # ---------------------------------------------------------

    if ml_available and llm_available:

        # ---------------------------------------------
        # Agreement
        # ---------------------------------------------

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
                "agreement": True,
                "human_review": False,
            }

        # ---------------------------------------------
        # Genuine disagreement
        # ---------------------------------------------

        return {
            "final_class": llm_class,
            "final_confidence": llm_confidence,
            "decision_mode": "ML_LLM_DISAGREEMENT",
            "ml": ml_result,
            "llm": llm_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 5. ML unavailable, LLM available
    # ---------------------------------------------------------

    if not ml_available and llm_available:

        return {
            "final_class": llm_class,
            "final_confidence": llm_confidence,
            "decision_mode": "LLM_ONLY_ML_UNAVAILABLE",
            "ml": ml_result,
            "llm": llm_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 6. ML available, LLM uncertain
    # ---------------------------------------------------------

    if ml_available and not llm_available:

        return {
            "final_class": ml_class,
            "final_confidence": ml_confidence,
            "decision_mode": "ML_ONLY_LLM_UNCERTAIN",
            "ml": ml_result,
            "llm": llm_result,
            "agreement": False,
            "human_review": True,
        }

    # ---------------------------------------------------------
    # 7. Neither model can classify the incident
    # ---------------------------------------------------------

    return {
        "final_class": "Unknown",
        "final_confidence": None,
        "decision_mode": "INSUFFICIENT_EVIDENCE",
        "ml": ml_result,
        "llm": llm_result,
        "agreement": False,
        "human_review": True,
    }