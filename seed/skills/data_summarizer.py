# ==========================================================
# FILE: data_summarizer.py
# PATH: SEED_ROOT/seed/skills/data_summarizer.py
# MODULE: Data Summarizer Skill v2.0
# SYSTEM READY: fully safe, metadata-rich, configurable
# ==========================================================

import time
import logging

logger = logging.getLogger("DataSummarizer")
logger.setLevel(logging.INFO)


def run(payload: dict) -> dict:
    # Ensure payload is a dictionary
    if not isinstance(payload, dict):
        logger.error("[DataSummarizer] Invalid payload type")
        return {
            "skill": "data_summarizer",
            "status": "error",
            "timestamp": time.time(),
            "metadata": {},
            "error": "Invalid payload type, expected dict"
        }

    text = payload.get("text", "")
    summary_sentences = payload.get("summary_sentences", 3)

    response = {
        "skill": "data_summarizer",
        "status": "unknown",
        "timestamp": time.time(),
        "metadata": {
            "length": len(text),
            "words": len(text.split()),
            "summary_sentences": summary_sentences
        },
        "data": {}
    }

    if not text.strip():
        response["status"] = "error"
        response["error"] = "No text provided"
        logger.warning("[DataSummarizer] Empty text received")
        return response

    try:
        # Naive summary: first N sentences
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        summary = ". ".join(sentences[:summary_sentences])
        if summary:
            summary += "."  # Ensure ending period
        response["status"] = "success"
        response["data"]["summary"] = summary
        response["metadata"]["sentence_count"] = len(sentences)
    except Exception as e:
        response["status"] = "error"
        response["error"] = str(e)
        logger.error(f"[DataSummarizer] Exception: {e}")

    return response
