"""Deterministic diff generation and noise reduction filters."""

import difflib
import re
from typing import Tuple

from app.crawler.extractor import normalize_text

COOKIE_CONSENT_KEYWORDS = [
    "cookie",
    "gdpr",
    "consent",
    "privacy preference",
    "accept all",
    "reject all",
    "cookie policy",
]


def generate_diff(
    previous_text: str,
    current_text: str,
    fromfile: str = "previous_snapshot",
    tofile: str = "current_snapshot",
) -> str:
    """Generate a clean unified text diff between two snapshot texts."""
    prev_lines = [line + "\n" for line in previous_text.splitlines()]
    curr_lines = [line + "\n" for line in current_text.splitlines()]

    diff_lines = list(
        difflib.unified_diff(
            prev_lines,
            curr_lines,
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )
    return "\n".join(diff_lines)


def summarize_diff(diff_text: str) -> str:
    """Produce a concise human-readable summary of additions and removals."""
    if not diff_text.strip():
        return "No changes detected"

    added = 0
    removed = 0
    sample_additions = []

    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
            cleaned = line[1:].strip()
            if cleaned and len(sample_additions) < 2:
                sample_additions.append(cleaned[:60])
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    summary_parts = []
    if added > 0:
        summary_parts.append(f"+{added} line{'s' if added != 1 else ''}")
    if removed > 0:
        summary_parts.append(f"-{removed} line{'s' if removed != 1 else ''}")

    summary = ", ".join(summary_parts) if summary_parts else "Minor changes"
    if sample_additions:
        summary += f": '{sample_additions[0]}...'"
    return summary


def is_meaningful_change(
    diff_text: str,
    previous_text: str,
    current_text: str,
) -> bool:
    """Evaluate whether detected diff represents meaningful business content.
    
    Filters obvious noise conservatively:
    - Empty or near-empty text (< 20 chars)
    - Normalized text is identical (whitespace-only changes)
    - Pure cookie banner / consent banners
    """
    # 1. Check if content differs only in whitespace
    if re.sub(r"\s+", " ", previous_text).strip() == re.sub(r"\s+", " ", current_text).strip():
        return False

    # 2. Check if current text is too short to be meaningful
    if len(current_text.strip()) < 20:
        return False

    # 3. Extract purely added or modified lines
    changed_lines = []
    for line in diff_text.splitlines():
        if (line.startswith("+") and not line.startswith("+++")) or (
            line.startswith("-") and not line.startswith("---")
        ):
            clean = line[1:].strip().lower()
            if clean:
                changed_lines.append(clean)

    if not changed_lines:
        return False

    # 4. Check if all changes are purely cookie / consent banner noise
    all_cookie_noise = True
    for line in changed_lines:
        if not any(keyword in line for keyword in COOKIE_CONSENT_KEYWORDS):
            all_cookie_noise = False
            break

    if all_cookie_noise:
        return False

    return True
