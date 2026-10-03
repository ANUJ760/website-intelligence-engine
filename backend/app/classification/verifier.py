"""Output and evidence verification against prompt injection or hallucination."""

import re
from typing import Tuple

from app.classification.schemas import SignalClassificationOutput, SignalType


def verify_evidence_in_content(evidence_quote: str, search_corpus: str) -> bool:
    """Verify that an evidence quote appears in the supplied text corpus."""
    if not evidence_quote.strip():
        return False

    clean_quote = re.sub(r"\s+", " ", evidence_quote.strip().lower())
    clean_corpus = re.sub(r"\s+", " ", search_corpus.lower())

    return clean_quote in clean_corpus


def verify_classification(
    output: SignalClassificationOutput,
    diff_text: str,
    current_text: str,
) -> Tuple[bool, str]:
    """Verify that the classifier output cites genuine evidence and follows rules.
    
    Returns (is_valid, message).
    """
    # 1. Category check (guaranteed by Pydantic Enum, but double checked)
    if not isinstance(output.change_type, SignalType):
        return False, f"Invalid signal category '{output.change_type}'"

    # For NO_SIGNAL or OTHER with no evidence, it's valid
    if output.change_type in (SignalType.NO_SIGNAL, SignalType.OTHER) and not output.evidence:
        return True, "Valid non-signal/other classification"

    # 2. Evidence presence check
    if not output.evidence:
        return False, "Classification requires cited evidence from page content or diff"

    # 3. Evidence substring verification against untrusted inputs
    corpus = f"{diff_text}\n\n{current_text}"
    for quote in output.evidence:
        if not verify_evidence_in_content(quote, corpus):
            return False, f"Evidence quote not found in page content or diff: '{quote}'"

    return True, "Classification and evidence verified"
