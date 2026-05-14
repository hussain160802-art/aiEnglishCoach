"""
learning_path_generator.py

Generates a structured LearningPath with WeeklyPlan and DailyPlan records
for a given user based on their assessment results and preferences.

Public entry point
------------------
generate_learning_path(request, assessment_result, db) -> LearningPath

The function is pure in the sense that it only reads from the DB (syllabus,
existing records) and writes the new LearningPath hierarchy; it never
calls an external LLM.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.learning_path import DailyPlan, LearningPath, WeeklyPlan
from app.models.syllabus import SyllabusSubtopic, SyllabusTopic
from app.schemas.assessment_schema import AnalysisResult
from app.schemas.learning_path_schema import LearningPathGenerateRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# CEFR level ordering used for gap calculations
CEFR_LEVELS: list[str] = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Skill category labels that map to SyllabusTopic.category values
SKILL_CATEGORIES: list[str] = [
    "grammar",
    "vocabulary",
    "reading",
    "listening",
    "speaking",
    "writing",
    "pronunciation",
]

# Minutes of study per day assumed when distributing weekly hours
DAYS_PER_WEEK: int = 5

# Minimum / maximum minutes for a single daily plan
MIN_DAILY_MINUTES: int = 15
MAX_DAILY_MINUTES: int = 120

# Default total weeks when not supplied by the caller
DEFAULT_TOTAL_WEEKS: int = 12

# Skill weights used to prioritise which skills get more time each week.
# Values are relative (they are normalised before use).
_DEFAULT_SKILL_WEIGHTS: dict[str, float] = {
    "grammar": 1.0,
    "vocabulary": 1.0,
    "reading": 0.8,
    "listening": 0.8,
    "speaking": 1.0,
    "writing": 1.0,
    "pronunciation": 0.4,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cefr_index(level: str) -> int:
    """Return 0-based index of *level* in CEFR_LEVELS (A1=0 … C2=5)."""
    try:
        return CEFR_LEVELS.index(level.upper())
    except ValueError:
        return 0


def _levels_between(current: str, target: str) -> list[str]:
    """Return the CEFR levels that need to be covered, inclusive of *target*."""
    start = _cefr_index(current)
    end = _cefr_index(target)
    if end <= start:
        # Already at or above target – still return at least the target level
        return [target.upper()]
    return CEFR_LEVELS[start : end + 1]


def _skill_score(analysis: AnalysisResult | None, skill: str) -> float:
    """
    Return the 0–100 score for *skill* from *analysis*.
    Falls back to 50.0 if analysis is None or the skill is absent.
    """
    if analysis is None:
        return 50.0
    mapping = {
        "grammar": analysis.grammar_score,
        "vocabulary": analysis.vocabulary_score,
        "reading": analysis.reading_score,
        "listening": analysis.listening_score,
        "speaking": analysis.speaking_score,
        "writing": analysis.writing_score,
    }
    val = mapping.get(skill.lower())
    return float(val) if val is not None else 50.0


def _build_skill_weights(
    analysis: AnalysisResult | None,
    focus_areas: list[str],
) -> dict[str, float]:
    """
    Compute normalised skill weights.

    Skills with lower scores get proportionally more weight.
    Explicitly requested *focus_areas* receive an additional 1.5× boost.
    """
    weights: dict[str, float] = {}
    for skill in SKILL_CATEGORIES:
        score = _skill_score(analysis, skill)
        # Invert score: lower score → higher weight
        base = max(0.1, (100.0 - score) / 100.0) * _DEFAULT_SKILL_WEIGHTS.get(skill, 1.0)
        if skill in [fa.lower() for fa in focus_areas]:
            base *= 1.5
        weights[skill] = base

    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def _fetch_subtopics_for_levels(
    db: Session,
    cefr_levels: list[str],
    focus_areas: list[str],
) -> list[SyllabusSubtopic]:
    """
    Return all active SyllabusSubtopic records that belong to the given
    CEFR levels and (optionally) match the focus_areas skill categories.
    Results are ordered by level order → topic order → subtopic order.
    """
    from app.models.syllabus import SyllabusLevel  # local import to avoid circulars

    query = (
        db.query(SyllabusSubtopic)
        .join(SyllabusSubtopic.topic)
        .join(SyllabusTopic.level)
        .filter(SyllabusSubtopic.is_active.is_(True))
        .filter(SyllabusTopic.is_active.is_(True))
        .filter(SyllabusLevel.code.in_([lvl.upper() for lvl in cefr_levels]))
    )

    if focus_areas:
        normalised = [fa.lower() for fa in focus_areas]
        query = query.filter(SyllabusTopic.category.in_(normalised))

    from app.models.syllabus import SyllabusLevel as _SL

    query = query.order_by(
        _SL.order,
        SyllabusTopic.order,
        SyllabusSubtopic.order,
    )
    return query.all()


def _distribute_subtopics(
    subtopics: list[SyllabusSubtopic],
    total_weeks: int,
    skill_weights: dict[str, float],
) -> list[list[SyllabusSubtopic]]:
    """
    Distribute *subtopics* across *total_weeks* buckets.

    Skill weights influence how many subtopics of each category are placed
    in earlier weeks (higher-weight skills appear sooner and more often).
    Returns a list of length *total_weeks*, each element being a list of
    SyllabusSubtopic objects assigned to that week.
    """
    if not subtopics:
        return [[] for _ in range(total_weeks)]

    # Group subtopics by skill category
    by_skill: dict[str, list[SyllabusSubtopic]] = {}
    for st in subtopics:
        cat = st.topic.category.lower() if st.topic and st.topic.category else "general"
        by_skill.setdefault(cat, []).append(st)

    # Build a weighted interleaved list
    ordered: list[SyllabusSubtopic] = []
    # Sort skills by weight descending so high-priority skills appear first
    sorted_skills = sorted(skill_weights.items(), key=lambda x: x[1], reverse=True)
    remaining = {k: list(v) for k, v in by_skill.items()}

    while any(remaining.values()):
        for skill, _ in sorted_skills:
            bucket = remaining.get(skill, [])
            if bucket:
                ordered.append(bucket.pop(0))

    # Split into equal-ish weekly buckets
    per_week = max(1, math.ceil(len(ordered) / total_weeks))
    weekly_buckets: list[list[SyllabusSubtopic]] = []
    for i in range(total_weeks):
        start = i * per_week
        weekly_buckets.append(ordered[start : start + per_week])

    return weekly_buckets


def _minutes_for_week(
    hours_per_week: float,
    week_index: int,
    total_weeks: int,
) -> int:
    """
    Return the total study minutes allocated for *week_index* (0-based).

    A gentle ramp-up is applied for the first quarter of the course and a
    slight taper for the last quarter (revision / consolidation phase).
    """
    base = int(hours_per_week * 60)
    ramp_weeks = max(1, total_weeks // 4)
    taper_start = total_weeks - ramp_weeks

    if week_index < ramp_weeks:
        factor = 0.7 + 0.3 * (week_index / ramp_weeks)
    elif week_index >= taper_start:
        factor = 0.9
    else:
        factor = 1.0

    return max(MIN_DAILY_MINUTES * DAYS_PER_WEEK, int(base * factor))


def _build_daily_plans(
    weekly_plan: WeeklyPlan,
    week_subtopics: list[SyllabusSubtopic],
    total_minutes: int,
    skill_weights: dict[str, float],
    start_date: datetime | None,
    week_index: int,
) -> list[DailyPlan]:
    """
    Create DailyPlan ORM objects (not yet added to the session) for the
    given *weekly_plan*.
    """
    daily_plans: list[DailyPlan] = []
    minutes_per_day = min(
        MAX_DAILY_MINUTES,
        max(MIN_DAILY_MINUTES, total_minutes // DAYS_PER_WEEK),
    )

    # Distribute subtopics across days
    per_day = max(1, math.ceil(len(week_subtopics) / DAYS_PER_WEEK)) if week_subtopics else 1
    # Determine the dominant skill for each day by cycling through sorted weights
    sorted_skills = sorted(skill_weights.items(), key=lambda x: x[1], reverse=True)
    skill_cycle = [s for s, _ in sorted_skills] or ["grammar"]

    for day_num in range(1, DAYS_PER_WEEK + 1):
        start = (day_num - 1) * per_day
        day_subtopics = week_subtopics[start : start + per_day]
        subtopic_ids = [st.id for st in day_subtopics]

        focus_skill = skill_cycle[(day_num - 1) % len(skill_cycle)]

        # Scheduled date (optional)
        scheduled_date: datetime | None = None
        if start_date is not None:
            offset_days = week_index * 7 + (day_num - 1)
            scheduled_date = start_date + timedelta(days=offset_days)

        # Build a human-readable title
        skill_label = focus_skill.capitalize()
        if day_subtopics:
            topic_names = ", ".join(
                st.topic.name if st.topic else st.name for st in day_subtopics[:2]
            )
            title = f"Day {day_num}: {skill_label} – {topic_names}"
            description = (
                f"Practice {skill_label.lower()} through "
                + ", ".join(st.name for st in day_subtopics)
            )
        else:
            title = f"Day {day_num}: {skill_label} Review"
            description = f"General {skill_label.lower()} review and consolidation."

        daily_plan = DailyPlan(
            weekly_plan=weekly_plan,
            day_number=day_num,
            title=title,
            description=description,
            focus_skill=focus_skill,
            subtopic_ids=subtopic_ids,
            exercise_ids=[],
            total_minutes=minutes_per_day,
            is_completed=False,
            completion_percentage=0.0,
            performance_score=None,
            notes=None,
            scheduled_date=scheduled_date,
            completed_at=None,
        )
        daily_plans.append(daily_plan)

    return daily_plans


def _build_weekly_plan(
    learning_path: LearningPath,
    week_number: int,
    week_subtopics: list[SyllabusSubtopic],
    total_minutes: int,
    skill_weights: dict[str, float],
    start_date: datetime | None,
) -> WeeklyPlan:
    """
    Create a WeeklyPlan ORM object (not yet flushed) with its DailyPlan
    children attached.
    """
    week_index = week_number - 1  # 0-based for date arithmetic

    # Collect topic names and subtopic IDs for metadata
    topic_names: list[str] = []
    subtopic_ids: list[int] = []
    for st in week_subtopics:
        subtopic_ids.append(st.id)
        if st.topic and st.topic.name not in topic_names:
            topic_names.append(st.topic.name)

    # Derive dominant skills for this week
    skill_counts: dict[str, int] = {}
    for st in week_subtopics:
        cat = st.topic.category.lower() if st.topic and st.topic.category else "general"
        skill_counts[cat] = skill_counts.get(cat, 0) + 1
    focus_topics = sorted(skill_counts, key=lambda k: skill_counts[k], reverse=True)[:3]

    goals = [
        f"Complete all {DAYS_PER_WEEK} daily sessions for week {week_number}.",
        f"Cover topics: {', '.join(topic_names[:4]) or 'general review'}.",
        "Achieve at least 70% on all exercises.",
    ]

    title = f"Week {week_number}: {', '.join(topic_names[:2]) or 'Review & Practice'}"
    description = (
        f"Week {week_number} covers {len(week_subtopics)} subtopics "
        f"across {len(topic_names)} topic(s). "
        f"Total study time: {total_minutes} minutes."
    )

    weekly_plan = WeeklyPlan(
        learning_path=learning_path,
        week_number=week_number,
        title=title,
        description=description,
        focus_topics=focus_topics,
        subtopic_ids=subtopic_ids,
        goals=goals,
        total_minutes=total_minutes,
        is_completed=False,
        completion_percentage=0.0,
        started_at=None,
        completed_at=None,
    )

    daily_plans = _build_daily_plans(
        weekly_plan=weekly_plan,
        week_subtopics=week_subtopics,
        total_minutes=total_minutes,
        skill_weights=skill_weights,
        start_date=start_date,
        week_index=week_index,
    )
    weekly_plan.daily_plans = daily_plans

    return weekly_plan


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_learning_path(
    request: LearningPathGenerateRequest,
    analysis: AnalysisResult | None,
    db: Session,
    start_date: datetime | None = None,
) -> LearningPath:
    """
    Generate a complete LearningPath with WeeklyPlan and DailyPlan children.

    Parameters
    ----------
    request:
        Validated request object containing user_id, assessment_id,
        target_level, hours_per_week, focus_areas, and total_weeks.
    analysis:
        The AnalysisResult from assessment_analyzer.analyze_assessment().
        May be None; in that case neutral weights and B1 current level
        are assumed.
    db:
        SQLAlchemy session.  The generated objects are added to the session
        but the caller is responsible for committing.
    start_date:
        Optional date from which to schedule daily plans.  Defaults to
        today (UTC) if None.

    Returns
    -------
    LearningPath
        The root ORM object with all children populated (but not yet
        committed to the DB).
    """
    if start_date is None:
        start_date = datetime.utcnow()

    current_level: str = (
        analysis.detected_level if analysis and analysis.detected_level else "A1"
    )
    target_level: str = request.target_level.upper()
    total_weeks: int = request.total_weeks or DEFAULT_TOTAL_WEEKS
    hours_per_week: float = request.hours_per_week or 5.0
    focus_areas: list[str] = [fa.lower() for fa in (request.focus_areas or [])]

    logger.info(
        "Generating learning path: user=%s current=%s target=%s weeks=%d h/w=%.1f",
        request.user_id,
        current_level,
        target_level,
        total_weeks,
        hours_per_week,
    )

    # 1. Determine which CEFR levels to cover
    levels_to_cover = _levels_between(current_level, target_level)

    # 2. Build skill weights from assessment scores + focus areas
    skill_weights = _build_skill_weights(analysis, focus_areas)

    # 3. Fetch syllabus subtopics for the relevant levels
    subtopics = _fetch_subtopics_for_levels(db, levels_to_cover, focus_areas)
    logger.info("Fetched %d subtopics for levels %s", len(subtopics), levels_to_cover)

    # 4. Distribute subtopics across weeks
    weekly_buckets = _distribute_subtopics(subtopics, total_weeks, skill_weights)

    # 5. Build title / description for the learning path
    lp_title = (
        f"English Learning Path: {current_level} → {target_level} "
        f"({total_weeks} weeks)"
    )
    focus_label = (
        ", ".join(fa.capitalize() for fa in focus_areas) if focus_areas else "All skills"
    )
    lp_description = (
        f"A {total_weeks}-week personalised English learning path "
        f"taking you from {current_level} to {target_level}. "
        f"Focus areas: {focus_label}. "
        f"Study time: {hours_per_week:.1f} hours per week."
    )

    # 6. Create the LearningPath ORM object
    learning_path = LearningPath(
        user_id=request.user_id,
        assessment_id=request.assessment_id,
        title=lp_title,
        description=lp_description,
        target_level=target_level,
        current_level=current_level,
        total_weeks=total_weeks,
        hours_per_week=hours_per_week,
        focus_areas=focus_areas,
        is_active=True,
        is_completed=False,
        started_at=start_date,
        completed_at=None,
    )

    # 7. Build weekly plans with daily plans
    weekly_plans: list[WeeklyPlan] = []
    for week_number in range(1, total_weeks + 1):
        bucket = weekly_buckets[week_number - 1] if week_number - 1 < len(weekly_buckets) else []
        week_minutes = _minutes_for_week(hours_per_week, week_number - 1, total_weeks)
        weekly_plan = _build_weekly_plan(
            learning_path=learning_path,
            week_number=week_number,
            week_subtopics=bucket,
            total_minutes=week_minutes,
            skill_weights=skill_weights,
            start_date=start_date,
        )
        weekly_plans.append(weekly_plan)

    learning_path.weekly_plans = weekly_plans

    # 8. Persist to the session (caller commits)
    db.add(learning_path)
    logger.info(
        "Learning path created: %d weekly plans, %d total daily plans",
        len(weekly_plans),
        sum(len(wp.daily_plans) for wp in weekly_plans),
    )

    return learning_path


def get_level_gap(current_level: str, target_level: str) -> int:
    """
    Return the number of CEFR steps between *current_level* and *target_level*.
    Negative if current > target.
    """
    return _cefr_index(target_level) - _cefr_index(current_level)


def estimate_total_weeks(
    current_level: str,
    target_level: str,
    hours_per_week: float = 5.0,
) -> int:
    """
    Rough estimate of the number of weeks required to progress from
    *current_level* to *target_level* at *hours_per_week* study hours.

    Based on commonly cited ~200 h per CEFR step guideline.
    """
    HOURS_PER_STEP = 200
    gap = get_level_gap(current_level, target_level)
    if gap <= 0:
        return DEFAULT_TOTAL_WEEKS
    total_hours = gap * HOURS_PER_STEP
    weeks = math.ceil(total_hours / max(1.0, hours_per_week))
    # Clamp to a sensible range
    return max(4, min(weeks, 104))
