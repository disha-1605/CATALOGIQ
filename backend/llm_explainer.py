"""LLM Explanation Engine for CatalogIQ.

Provides plain-language executive summaries and actionable PM recommendations
from deterministic diagnostic metrics. Supports Google Gemini API (GEMINI_API_KEY)
and OpenAI-compatible APIs (OPENAI_API_KEY / LLM_API_KEY) with direct HTTP via httpx,
backed by an automatic deterministic fallback generator on any failure.
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

logger = logging.getLogger("catalogiq.llm_explainer")


def generate_template_fallback_explanation(data: Dict[str, Any]) -> str:
    """
    Deterministic template-based explanation generated directly from structured metrics.
    Ensures 100% endpoint reliability even when no LLM API key is present or on network failure.
    """
    query = data.get("query", "")
    volume = data.get("search_volume", data.get("impressions", 0))
    ctr_pct = round(data.get("ctr", 0.0) * 100, 2)
    cvr_pct = round(data.get("conversion_rate", 0.0) * 100, 2)
    cov_pct = round(data.get("catalog_coverage", 0.0) * 100, 1)
    root_cause = data.get("root_cause", "NO_CATALOG_GAP_DETECTED")
    opp_score = data.get("opportunity_score", 0.0)
    affected = data.get("affected_products", data.get("affected_products_count", 0))
    missing_breakdown = data.get("missing_attributes_breakdown", {})
    
    missing_str = ", ".join(missing_breakdown.keys()) if missing_breakdown else "critical attributes"

    if root_cause == "ATTRIBUTE_GAP":
        return (
            f"The search query '{query}' generates {volume:,} monthly impressions with a low CTR of {ctr_pct}% "
            f"and conversion rate of {cvr_pct}%. While relevant inventory exists, discovery coverage is restricted "
            f"to {cov_pct}% because {affected} catalog products are missing {missing_str} tags. "
            f"This attribute gap represents an opportunity score of {opp_score}/100, and enriching these metadata attributes will "
            f"immediately restore search discoverability."
        )
    elif root_cause == "INVENTORY_GAP":
        return (
            f"The search query '{query}' records strong customer demand ({volume:,} monthly searches) but suffers "
            f"from an inventory gap with fewer than 4 relevant products available in the active catalog. "
            f"With a {cvr_pct}% conversion rate on limited clicks, this presents an opportunity score of {opp_score}/100. "
            f"The merchandising team should prioritize procuring or onboarding inventory in this category to capture unmet demand."
        )
    else:
        return (
            f"The search query '{query}' exhibits healthy catalog discovery with {cov_pct}% coverage across active products. "
            f"Current performance shows {volume:,} impressions with a {ctr_pct}% CTR and {cvr_pct}% conversion rate, "
            f"yielding a baseline opportunity score of {opp_score}/100. "
            f"No immediate catalog or inventory remediation is required; continue standard monitoring."
        )


def _call_gemini_api(prompt: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Call Google Gemini generateContent REST endpoint using direct HTTP via httpx."""
    # Preferred default model for sub-2s latency and high-quality structured analysis
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "systemInstruction": {
            "parts": [{
                "text": (
                    "You are a concise e-commerce catalog operations analyst. "
                    "Maintain a neutral, professional business analyst tone. "
                    "Do not use marketing buzzwords, exclamation points, or phrases like 'AI-powered'."
                )
            }]
        },
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
        }
    }

    headers = {"Content-Type": "application/json"}
    
    with httpx.Client(timeout=4.5) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            resp_json = response.json()
            candidates = resp_json.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts and "text" in parts[0]:
                    content = parts[0]["text"].strip()
                    return {
                        "explanation": content,
                        "source": "llm",
                        "model": model,
                    }
        else:
            logger.warning(f"Gemini API returned HTTP {response.status_code}: {response.text}")
    return None


def _call_openai_api(prompt: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Call OpenAI-compatible chat completions endpoint."""
    api_base = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise e-commerce catalog business analyst."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 200,
        "temperature": 0.2,
    }

    with httpx.Client(timeout=4.0) as client:
        response = client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"].strip()
            return {
                "explanation": content,
                "source": "llm",
                "model": model,
            }
        else:
            logger.warning(f"OpenAI API returned HTTP {response.status_code}: {response.text}")
    return None


def generate_llm_explanation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate plain-language business analyst explanation.
    Tries configured LLM API (Gemini or OpenAI); falls back to deterministic template on any failure.
    
    Provider Precedence:
    If GEMINI_API_KEY is configured, Google Gemini API is used.
    Else if OPENAI_API_KEY or LLM_API_KEY is configured, OpenAI-compatible API is used.
    Otherwise, deterministic template fallback is returned immediately.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")

    # If no API key configured, use deterministic template immediately
    if not gemini_key and not openai_key:
        fallback_text = generate_template_fallback_explanation(data)
        return {
            "explanation": fallback_text,
            "source": "template_fallback",
            "model": "rule-based-template",
        }

    prompt = (
        "You are an e-commerce catalog operations analyst. Write a concise 2-4 sentence explanation "
        "of the following search diagnostics data for product managers. "
        "Maintain a neutral, professional business analyst tone. Do not use marketing buzzwords, exclamation points, "
        "or phrases like 'AI-powered'. Explain why this issue matters and the concrete recommended action.\n\n"
        f"Search Query: {data.get('query')}\n"
        f"Monthly Search Volume: {data.get('search_volume')}\n"
        f"Click-Through Rate (CTR): {round(data.get('ctr', 0)*100, 2)}%\n"
        f"Conversion Rate: {round(data.get('conversion_rate', 0)*100, 2)}%\n"
        f"Relevant Products Count: {data.get('relevant_products')}\n"
        f"Catalog Coverage: {round(data.get('catalog_coverage', 0)*100, 1)}%\n"
        f"Root Cause: {data.get('root_cause')}\n"
        f"Opportunity Score: {data.get('opportunity_score')}/100\n"
        f"Affected Defective Products: {data.get('affected_products')}\n"
        f"Missing Attributes Breakdown: {json.dumps(data.get('missing_attributes_breakdown', {}))}\n"
        f"Recommended Action: {data.get('recommended_action')}\n"
    )

    try:
        if gemini_key:
            res = _call_gemini_api(prompt, gemini_key)
            if res:
                return res
        elif openai_key:
            res = _call_openai_api(prompt, openai_key)
            if res:
                return res
    except Exception as exc:
        logger.warning(f"LLM API execution failed: {exc}. Falling back to deterministic template.")

    # Graceful Fallback
    fallback_text = generate_template_fallback_explanation(data)
    return {
        "explanation": fallback_text,
        "source": "template_fallback",
        "model": "rule-based-template",
    }
