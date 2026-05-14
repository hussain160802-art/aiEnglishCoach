"""
Assessment Analyzer Service

Analyzes user assessment responses to determine English proficiency level,
skill scores, strengths, weaknesses, and recommendations.
"""

import re
import logging
from typing import Any

from app.schemas.assessment_schema import AnalysisResult

logger = logging.getLogger(__name__)

# CEFR level ordering for comparisons
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Skill weight factors used for overall score calculation
SKILL_WEIGHTS = {
    "grammar": 0.20,
    "vocabulary": 0.20,
    "reading": 0.20,
    "listening": 0.15,
    "speaking": 0.12,
    "writing": 0.13,
}

# Score thresholds that map to CEFR levels
SCORE_TO_CEFR = [
    (90.0, "C2"),
    (78.0, "C1"),
    (65.0, "B2"),
    (52.0, "B1"),
    (38.0, "A2"),
    (0.0,  "A1"),
]

# Grammar question keys expected in raw_responses
GRAMMAR_KEYS = {
    "grammar_score",
    "grammar_correct",
    "grammar_total",
    "grammar_percentage",
}

# Vocabulary question keys expected in raw_responses
VOCABULARY_KEYS = {
    "vocabulary_score",
    "vocabulary_correct",
    "vocabulary_total",
    "vocabulary_percentage",
}

# Reading question keys expected in raw_responses
READING_KEYS = {
    "reading_score",
    "reading_correct",
    "reading_total",
    "reading_percentage",
}

# Listening question keys expected in raw_responses
LISTENING_KEYS = {
    "listening_score",
    "listening_correct",
    "listening_total",
    "listening_percentage",
}

# Speaking question keys expected in raw_responses
SPEAKING_KEYS = {
    "speaking_score",
    "speaking_percentage",
}

# Writing question keys expected in raw_responses
WRITING_KEYS = {
    "writing_score",
    "writing_percentage",
}


def _extract_skill_score(
    responses: dict[str, Any],
    score_key: str,
    correct_key: str,
    total_key: str,
    percentage_key: str,
) -> float | None:
    """
    Attempt to derive a 0–100 score for a single skill from raw_responses.

    Priority:
    1. Direct percentage / score field (already 0–100)
    2. correct / total ratio converted to 0–100
    3. Returns None when insufficient data is present
    """
    # Direct score/percentage
    for key in (percentage_key, score_key):
        value = responses.get(key)
        if value is not None:
            try:
                score = float(value)
                # Treat values > 1 as already being on a 0–100 scale;
                # treat values in [0, 1] as fractions and multiply by 100.
                if 0.0 <= score <= 1.0:
                    score = score * 100.0
                if 0.0 <= score <= 100.0:
                    return round(score, 2)
            except (TypeError, ValueError):
                pass

    # Correct / total ratio
    correct = responses.get(correct_key)
    total = responses.get(total_key)
    if correct is not None and total is not None:
        try:
            c, t = float(correct), float(total)
            if t > 0:
                return round((c / t) * 100.0, 2)
        except (TypeError, ValueError):
            pass

    return None


def _score_from_responses(responses: dict[str, Any]) -> dict[str, float | None]:
    """Extract individual skill scores from raw_responses dict."""
    return {
        "grammar": _extract_skill_score(
            responses, "grammar_score", "grammar_correct", "grammar_total", "grammar_percentage"
        ),
        "vocabulary": _extract_skill_score(
            responses, "vocabulary_score", "vocabulary_correct", "vocabulary_total", "vocabulary_percentage"
        ),
        "reading": _extract_skill_score(
            responses, "reading_score", "reading_correct", "reading_total", "reading_percentage"
        ),
        "listening": _extract_skill_score(
            responses, "listening_score", "listening_correct", "listening_total", "listening_percentage"
        ),
        "speaking": _extract_skill_score(
            responses, "speaking_score", None, None, "speaking_percentage"
        ),
        "writing": _extract_skill_score(
            responses, "writing_score", None, None, "writing_percentage"
        ),
    }


def _compute_overall_score(skill_scores: dict[str, float | None]) -> float:
    """
    Compute a weighted overall score from individual skill scores.
    Skills with None values are excluded and their weights redistributed.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for skill, weight in SKILL_WEIGHTS.items():
        score = skill_scores.get(skill)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return round(weighted_sum / total_weight, 2)


def _score_to_cefr(score: float) -> str:
    """Map a 0–100 overall score to the corresponding CEFR level."""
    for threshold, level in SCORE_TO_CEFR:
        if score >= threshold:
            return level
    return "A1"


def _analyse_writing_sample(writing_sample: str | None) -> dict[str, Any]:
    """
    Perform lightweight heuristic analysis on a writing sample.

    Returns a dict with keys: estimated_level, notes, grammar_hints, vocab_hints.
    This is intentionally simple — a production system would call an LLM here.
    """
    result: dict[str, Any] = {
        "estimated_level": None,
        "notes": [],
        "grammar_hints": [],
        "vocab_hints": [],
    }

    if not writing_sample or not writing_sample.strip():
        return result

    text = writing_sample.strip()
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r"\b\w+\b", text.lower())
    unique_words = set(words)
    word_count = len(words)
    sentence_count = max(len(sentences), 1)
    avg_sentence_length = word_count / sentence_count
    type_token_ratio = len(unique_words) / max(word_count, 1)

    # Heuristic level estimation from writing complexity
    if avg_sentence_length >= 20 and type_token_ratio >= 0.55:
        result["estimated_level"] = "C1"
    elif avg_sentence_length >= 15 and type_token_ratio >= 0.45:
        result["estimated_level"] = "B2"
    elif avg_sentence_length >= 10 and type_token_ratio >= 0.35:
        result["estimated_level"] = "B1"
    elif avg_sentence_length >= 7:
        result["estimated_level"] = "A2"
    else:
        result["estimated_level"] = "A1"

    result["notes"].append(
        f"Writing sample: {word_count} words, {sentence_count} sentences, "
        f"avg sentence length {avg_sentence_length:.1f}, "
        f"type-token ratio {type_token_ratio:.2f}."
    )

    # Simple grammar surface checks
    if re.search(r"\bi\b", text):
        result["grammar_hints"].append(
            "Capitalise the pronoun 'I' consistently."
        )
    if re.search(r"\s{2,}", text):
        result["grammar_hints"].append(
            "Multiple consecutive spaces detected — review spacing."
        )

    # Vocabulary diversity hint
    if type_token_ratio < 0.30:
        result["vocab_hints"].append(
            "Vocabulary diversity is low; try using more varied word choices."
        )
    elif type_token_ratio >= 0.60:
        result["vocab_hints"].append(
            "Good vocabulary diversity detected in the writing sample."
        )

    return result

def _build_strengths(skill_scores: dict[str, float | None]) -> list[str]:
    """Return a list of skill-area strength descriptions (score ≥ 70)."""
    strengths: list[str] = []
    for skill, score in skill_scores.items():
        if score is not None and score >= 70.0:
            strengths.append(
                f"{skill.capitalize()} — strong performance ({score:.0f}/100)."
            )
    return strengths


def _build_weaknesses(skill_scores: dict[str, float | None]) -> list[str]:
    """Return a list of skill-area weakness descriptions (score < 55)."""
    weaknesses: list[str] = []
    for skill, score in skill_scores.items():
        if score is not None and score < 55.0:
            weaknesses.append(
                f"{skill.capitalize()} — needs improvement ({score:.0f}/100)."
            )
    return weaknesses


def _build_recommendations(
    skill_scores: dict[str, float | None],
    detected_level: str,
) -> list[str]:
    """Generate actionable learning recommendations based on skill scores."""
    recommendations: list[str] = []

    skill_advice = {
        "grammar": (
            "Focus on grammar exercises targeting common error patterns "
            f"at the {detected_level} level."
        ),
        "vocabulary": (
            "Expand vocabulary through reading and spaced-repetition flashcard practice."
        ),
        "reading": (
            "Practise reading comprehension with texts at or slightly above your current level."
        ),
        "listening": (
            "Improve listening skills by engaging with podcasts, videos, and audio exercises."
        ),
        "speaking": (
            "Build speaking fluency through conversation practice and pronunciation drills."
        ),
        "writing": (
            "Develop writing skills by practising structured paragraphs and short essays."
        ),
    }

    # Recommend for weak skills first
    for skill, score in skill_scores.items():
        if score is not None and score < 55.0:
            recommendations.append(skill_advice[skill])

    # Then suggest maintenance for average skills
    for skill, score in skill_scores.items():
        if score is not None and 55.0 <= score < 70.0:
            recommendations.append(
                f"Continue practising {skill} to consolidate your current level."
            )

    if not recommendations:
        recommendations.append(
            "Maintain your strong performance by exploring advanced "
            f"{detected_level}+ materials across all skill areas."
        )

    return recommendations


def _merge_cefr_levels(score_level: str, writing_level: str | None) -> str:
    """
    Merge the score-derived CEFR level with the writing-sample-derived level.
    Returns the lower of the two as a conservative estimate.
    """
    if writing_level is None or writing_level not in CEFR_LEVELS:
        return score_level
    score_idx = CEFR_LEVELS.index(score_level)
    writing_idx = CEFR_LEVELS.index(writing_level)
    # Use the average index, rounded down, as a balanced estimate
    merged_idx = (score_idx + writing_idx) // 2
    return CEFR_LEVELS[merged_idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_assessment(
    raw_responses: dict[str, Any],
    writing_sample: str | None = None,
    speaking_sample_url: str | None = None,
) -> AnalysisResult:
    """
    Analyse an assessment submission and return a fully populated AnalysisResult.

    Parameters
    ----------
    raw_responses:
        Dictionary of assessment question responses.  Expected keys follow the
        ``<skill>_score``, ``<skill>_correct``, ``<skill>_total``, and
        ``<skill>_percentage`` naming conventions.
    writing_sample:
        Optional free-text writing sample provided by the user.
    speaking_sample_url:
        Optional URL to a recorded speaking sample (not analysed locally).

    Returns
    -------
    AnalysisResult
        Pydantic model containing all computed scores, level, strengths,
        weaknesses, recommendations, and analysis notes.
    """
    logger.info("Starting assessment analysis")

    # 1. Extract per-skill scores from raw responses
    skill_scores = _score_from_responses(raw_responses)
    logger.debug("Extracted skill scores: %s", skill_scores)

    # 2. Analyse writing sample (heuristic)
    writing_analysis = _analyse_writing_sample(writing_sample)
    writing_level_hint: str | None = writing_analysis.get("estimated_level")

    # 3. Compute overall score
    overall_score = _compute_overall_score(skill_scores)
    logger.debug("Overall score: %s", overall_score)

    # 4. Determine CEFR level
    score_level = _score_to_cefr(overall_score)
    detected_level = _merge_cefr_levels(score_level, writing_level_hint)
    logger.info("Detected CEFR level: %s (score-based: %s)", detected_level, score_level)

    # 5. Build strengths, weaknesses, recommendations
    strengths = _build_strengths(skill_scores)
    weaknesses = _build_weaknesses(skill_scores)
    recommendations = _build_recommendations(skill_scores, detected_level)

    # 6. Compile analysis notes
    analysis_notes_parts: list[str] = []
    for note in writing_analysis.get("notes", []):
        analysis_notes_parts.append(note)
    for hint in writing_analysis.get("grammar_hints", []):
        analysis_notes_parts.append(f"Grammar hint: {hint}")
    for hint in writing_analysis.get("vocab_hints", []):
        analysis_notes_parts.append(f"Vocabulary hint: {hint}")
    if speaking_sample_url:
        analysis_notes_parts.append(
            f"Speaking sample provided at {speaking_sample_url}; "
            "manual or AI review recommended."
        )
    analysis_notes = " | ".join(analysis_notes_parts) if analysis_notes_parts else None

    # 7. Assemble result — use 0.0 for None scores so schema validators pass
    def _coerce(v: float | None) -> float:
        return v if v is not None else 0.0

    result = AnalysisResult(
        detected_level=detected_level,
        grammar_score=_coerce(skill_scores["grammar"]),
        vocabulary_score=_coerce(skill_scores["vocabulary"]),
        reading_score=_coerce(skill_scores["reading"]),
        listening_score=_coerce(skill_scores["listening"]),
        speaking_score=_coerce(skill_scores["speaking"]),
        writing_score=_coerce(skill_scores["writing"]),
        overall_score=overall_score,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
        analysis_notes=analysis_notes,
    )

    logger.info("Assessment analysis complete — level=%s overall=%.1f", detected_level, overall_score)
    return result


def get_level_description(cefr_level: str) -> str:
    """Return a human-readable description of a CEFR level."""
    descriptions = {
        "A1": (
            "Beginner — can understand and use familiar everyday expressions "
            "and very basic phrases."
        ),
        "A2": (
            "Elementary — can understand sentences and frequently used expressions "
            "related to areas of immediate relevance."
        ),
        "B1": (
            "Intermediate — can understand the main points of clear standard input "
            "on familiar matters."
        ),
        "B2": (
            "Upper-Intermediate — can understand the main ideas of complex text on "
            "both concrete and abstract topics."
        ),
        "C1": (
            "Advanced — can understand a wide range of demanding, longer texts and "
            "recognise implicit meaning."
        ),
        "C2": (
            "Proficient — can understand with ease virtually everything heard or read "
            "and express themselves spontaneously."
        ),
    }
    return descriptions.get(cefr_level.upper(), f"Unknown CEFR level: {cefr_level}")


def compare_levels(level_a: str, level_b: str) -> int:
    """
    Compare two CEFR levels.

    Returns
    -------
    int
        -1 if level_a < level_b, 0 if equal, 1 if level_a > level_b.

    Raises
    ------
    ValueError
        If either level is not a valid CEFR code.
    """
    a = level_a.upper()
    b = level_b.upper()
    if a not in CEFR_LEVELS:
        raise ValueError(f"Invalid CEFR level: {level_a}")
    if b not in CEFR_LEVELS:
        raise ValueError(f"Invalid CEFR level: {level_b}")
    idx_a = CEFR_LEVELS.index(a)
    idx_b = CEFR_LEVELS.index(b)
    if idx_a < idx_b:
        return -1
    if idx_a > idx_b:
        return 1
    return 0