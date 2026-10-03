"""Classifier interface, deterministic rule classifier, and LLM classifier implementations."""

from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Optional

import httpx

from app.config import settings
from app.classification.prompts import SYSTEM_PROMPT, PROMPT_VERSION, build_classification_prompt
from app.classification.schemas import SignalClassificationOutput, SignalType
from app.classification.verifier import verify_classification

logger = logging.getLogger(__name__)


class BaseClassifier(ABC):
    """Abstract interface for change classifiers."""

    @abstractmethod
    async def classify(
        self,
        company_name: str,
        domain: str,
        url: str,
        page_type: str,
        diff_text: str,
        current_text: str,
    ) -> SignalClassificationOutput:
        pass


class RuleBasedClassifier(BaseClassifier):
    """Deterministic, provider-independent classifier based on conservative keywords and evidence matching."""

    async def classify(
        self,
        company_name: str,
        domain: str,
        url: str,
        page_type: str,
        diff_text: str,
        current_text: str,
    ) -> SignalClassificationOutput:
        lower_diff = diff_text.lower()

        # 1. Pricing change pattern
        if any(w in lower_diff for w in ["$", "€", "£", "/month", "/mo", "pricing", "tier", "plan"]):
            # Find exact line in diff for evidence
            for line in diff_text.splitlines():
                if line.startswith("+") and any(w in line.lower() for w in ["$", "pricing", "month", "plan"]):
                    quote = line[1:].strip()
                    return SignalClassificationOutput(
                        change_type=SignalType.PRICING_CHANGE,
                        observed_change=f"Pricing or plan update detected: {quote}",
                        potential_business_signal=f"{company_name} may have updated their pricing structure or tier options.",
                        evidence=[quote],
                        confidence=0.85,
                    )

        # 2. Hiring expansion pattern
        if any(w in lower_diff for w in ["careers", "we're hiring", "job opening", "open roles", "join our team"]):
            for line in diff_text.splitlines():
                if line.startswith("+") and any(w in line.lower() for w in ["hiring", "job", "role", "career"]):
                    quote = line[1:].strip()
                    return SignalClassificationOutput(
                        change_type=SignalType.HIRING_EXPANSION,
                        observed_change=f"Hiring or career opportunity added: {quote}",
                        potential_business_signal=f"{company_name} appears to be expanding headcounts in key areas.",
                        evidence=[quote],
                        confidence=0.8,
                    )

        # 3. Product launch / announcement pattern
        if any(w in lower_diff for w in ["announcing", "introducing", "launching", "new feature", "now available"]):
            for line in diff_text.splitlines():
                if line.startswith("+") and any(w in line.lower() for w in ["announcing", "introducing", "launch", "feature"]):
                    quote = line[1:].strip()
                    return SignalClassificationOutput(
                        change_type=SignalType.PRODUCT_LAUNCH,
                        observed_change=f"Product announcement detected: {quote}",
                        potential_business_signal=f"{company_name} has introduced new functionality or products.",
                        evidence=[quote],
                        confidence=0.8,
                    )

        # 4. New Integration pattern
        if any(w in lower_diff for w in ["integration", "integrates with", "partner", "api connector"]):
            for line in diff_text.splitlines():
                if line.startswith("+") and any(w in line.lower() for w in ["integration", "integrat", "partner"]):
                    quote = line[1:].strip()
                    return SignalClassificationOutput(
                        change_type=SignalType.NEW_INTEGRATION,
                        observed_change=f"Integration update detected: {quote}",
                        potential_business_signal=f"{company_name} is extending ecosystem interoperability.",
                        evidence=[quote],
                        confidence=0.75,
                    )

        # 5. Default fallback to OTHER or NO_SIGNAL
        if len(diff_text.strip()) > 50:
            return SignalClassificationOutput(
                change_type=SignalType.OTHER,
                observed_change="General website text modifications observed without recognized commercial category.",
                potential_business_signal="Routine website maintenance or copy revisions.",
                evidence=[],
                confidence=0.3,
            )

        return SignalClassificationOutput(
            change_type=SignalType.NO_SIGNAL,
            observed_change="Minor non-commercial text edits detected.",
            potential_business_signal="No discernible strategic business changes.",
            evidence=[],
            confidence=0.1,
        )


class LLMClassifier(BaseClassifier):
    """Configurable LLM provider classifier with schema validation and fallback."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.fallback = RuleBasedClassifier()

    async def classify(
        self,
        company_name: str,
        domain: str,
        url: str,
        page_type: str,
        diff_text: str,
        current_text: str,
    ) -> SignalClassificationOutput:
        prompt = build_classification_prompt(
            company_name=company_name,
            domain=domain,
            url=url,
            page_type=page_type,
            diff_text=diff_text,
            current_text=current_text,
        )

        try:
            # Connect to Gemini REST endpoint (v1beta)
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]}
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed_json = json.loads(raw_text)
                    validated = SignalClassificationOutput.model_validate(parsed_json)

                    # Verify evidence
                    is_valid, reason = verify_classification(validated, diff_text, current_text)
                    if is_valid:
                        return validated
                    else:
                        logger.warning(f"LLM evidence verification failed: {reason}. Falling back to RuleClassifier.")
                        return await self.fallback.classify(company_name, domain, url, page_type, diff_text, current_text)
                else:
                    logger.warning(f"LLM API returned status {resp.status_code}. Using fallback classifier.")
                    return await self.fallback.classify(company_name, domain, url, page_type, diff_text, current_text)

        except Exception as exc:
            logger.warning(f"LLM classification encountered error: {exc}. Using fallback classifier.")
            return await self.fallback.classify(company_name, domain, url, page_type, diff_text, current_text)


def get_classifier() -> BaseClassifier:
    """Factory returning configured classifier."""
    if settings.AI_CLASSIFICATION_ENABLED and settings.LLM_API_KEY:
        return LLMClassifier(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL or "gemini-2.5-flash",
        )
    return RuleBasedClassifier()
