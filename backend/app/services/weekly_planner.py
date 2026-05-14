"""
weekly_planner.py

Service responsible for generating, updating, and querying WeeklyPlan objects
within an existing LearningPath.  It complements learning_path_generator.py
(which creates the full path at once) by providing fine-grained control over
individual weeks: regenerating a single week, rebalancing minutes, marking
completion, and computing progress statistics.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.learning_path import DailyPlan, LearningPath, WeeklyPlan
from app.models.syllabus import SyllabusSubtopic
from app.schemas.learning_path_schema import (
    DailyPlanGenerateRequest,
    WeeklyPlanGenerateRequest,
    WeeklyPlanResponse,
    WeeklyPlanSummary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAYS_PER_WEEK: int = 5  # Mon–Fri active learning days
MIN_DAILY_MINUTES: int = 15
MAX_DAILY_MINUTES: int = 120
DEFAULT_MINUTES_PER_WEEK: int = 300  # 5 hours

# Skill rotation order used when no explicit focus_skill is given
SKILL_ROTATION: list[str] = [
    "grammar",
    "vocabulary",
    "reading",
    "listening",
    "speaking",
    "writing",
]

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_weekly_plan(weekly_plan_id: int, db: Session) -> WeeklyPlan | None:
    """Return a WeeklyPlan by primary key, or None if not found."""
    return db.query(WeeklyPlan).filter(WeeklyPlan.id == weekly_plan_id).first()


def list_weekly_plans(
    learning_path_id: int,
    db: Session,
    *,
    include_completed: bool = True,
) -> list[WeeklyPlan]:
    """Return all WeeklyPlans for a LearningPath, ordered by week_number."""
    q = db.query(WeeklyPlan).filter(
        WeeklyPlan.learning_path_id == learning_path_id
    )
    if not include_completed:
        q = q.filter(WeeklyPlan.is_completed == False)  # noqa: E712
    return q.order_by(WeeklyPlan.week_number).all()


def get_current_week(learning_path_id: int, db: Session) -> WeeklyPlan | None:
    """
    Return the first incomplete WeeklyPlan for *learning_path_id*, or the
    last plan if all are completed.
    """
    plans = list_weekly_plans(learning_path_id, db, include_completed=True)
    if not plans:
        return None
    for plan in plans:
        if not plan.is_completed:
            return plan
    return plans[-1]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_weekly_plan(
    request: WeeklyPlanGenerateRequest,
    db: Session,
    *,
    start_date: date | None = None,
    commit: bool = False,
) -> WeeklyPlan:
    """
    Generate a new WeeklyPlan (with DailyPlan children) for an existing
    LearningPath.

    Parameters
    ----------
    request:
        ``WeeklyPlanGenerateRequest`` carrying ``learning_path_id``,
        ``week_number``, ``hours_available``, and optional ``focus_skill``.
    db:
        Active SQLAlchemy session.
    start_date:
        The calendar date of the first day of this week.  When omitted the
        function calculates it from ``LearningPath.started_at`` and
        ``week_number``.
    commit:
        When *True* the session is committed after the objects are added.
        Defaults to *False* so the caller can batch multiple operations.

    Returns
    -------
    WeeklyPlan
        The newly created (and db-added) WeeklyPlan instance.
    """
    learning_path: LearningPath | None = (
        db.query(LearningPath)
        .filter(LearningPath.id == request.learning_path_id)
        .first()
    )
    if learning_path is None:
        raise ValueError(
            f"LearningPath {request.learning_path_id} not found."
        )

    total_minutes = _hours_to_minutes(request.hours_available)
    week_start = _resolve_week_start(learning_path, request.week_number, start_date)

    subtopic_ids = _pick_subtopics_for_week(
        learning_path, request.week_number, db
    )
    focus_topics = _derive_focus_topics(subtopic_ids, db)

    weekly_plan = WeeklyPlan(
        learning_path_id=request.learning_path_id,
        week_number=request.week_number,
        title=f"Week {request.week_number}",
        description=(
            f"Week {request.week_number} of {learning_path.total_weeks}: "
            f"focus on {', '.join(focus_topics) or 'core skills'}."
        ),
        focus_topics=focus_topics,
        subtopic_ids=subtopic_ids,
        goals=_build_goals(focus_topics, learning_path.target_level),
        total_minutes=total_minutes,
        is_completed=False,
        completion_percentage=0.0,
    )
    db.add(weekly_plan)
    db.flush()  # populate weekly_plan.id before children reference it

    daily_plans = _build_daily_plans(
        weekly_plan=weekly_plan,
        total_minutes=total_minutes,
        subtopic_ids=subtopic_ids,
        focus_skill=request.focus_skill,
        week_start=week_start,
    )
    for dp in daily_plans:
        db.add(dp)

    if commit:
        db.commit()
        db.refresh(weekly_plan)

    logger.info(
        "Generated WeeklyPlan week=%d for LearningPath id=%d (%d daily plans, %d min)",
        request.week_number,
        request.learning_path_id,
        len(daily_plans),
        total_minutes,
    )
    return weekly_plan


# ---------------------------------------------------------------------------
# Progress & completion
# ---------------------------------------------------------------------------


def mark_weekly_plan_complete(
    weekly_plan_id: int,
    db: Session,
    *,
    performance_score: float | None = None,
    commit: bool = True,
) -> WeeklyPlan:
    """
    Mark a WeeklyPlan as completed and recompute ``completion_percentage``.

    Also advances ``LearningPath.is_completed`` if this was the final week.
    """
    plan = _get_or_raise(weekly_plan_id, db)
    plan.is_completed = True
    plan.completion_percentage = 100.0
    plan.completed_at = datetime.utcnow()

    # Propagate performance score to daily plans that lack one
    if performance_score is not None:
        for dp in plan.daily_plans:
            if dp.performance_score is None:
                dp.performance_score = performance_score

    _maybe_complete_learning_path(plan, db)

    if commit:
        db.commit()
        db.refresh(plan)
    return plan


def update_weekly_progress(
    weekly_plan_id: int,
    db: Session,
    *,
    commit: bool = True,
) -> WeeklyPlan:
    """
    Recompute ``completion_percentage`` for a WeeklyPlan based on the
    completion status of its DailyPlan children.
    """
    plan = _get_or_raise(weekly_plan_id, db)
    daily_plans = plan.daily_plans
    if not daily_plans:
        return plan

    completed = sum(1 for dp in daily_plans if dp.is_completed)
    plan.completion_percentage = round(completed / len(daily_plans) * 100, 2)

    if plan.completion_percentage >= 100.0:
        plan.is_completed = True
        plan.completed_at = plan.completed_at or datetime.utcnow()
        _maybe_complete_learning_path(plan, db)

    if commit:
        db.commit()
        db.refresh(plan)
    return plan


def rebalance_weekly_minutes(
    weekly_plan_id: int,
    new_total_minutes: int,
    db: Session,
    *,
    commit: bool = True,
) -> WeeklyPlan:
    """
    Redistribute ``new_total_minutes`` across the incomplete DailyPlans of a
    WeeklyPlan, respecting MIN/MAX per-day constraints.
    """
    plan = _get_or_raise(weekly_plan_id, db)
    incomplete_days = [dp for dp in plan.daily_plans if not dp.is_completed]
    if not incomplete_days:
        logger.warning(
            "rebalance_weekly_minutes: all days already completed for WeeklyPlan %d",
            weekly_plan_id,
        )
        return plan

    plan.total_minutes = new_total_minutes
    per_day = _clamp(
        new_total_minutes // len(incomplete_days),
        MIN_DAILY_MINUTES,
        MAX_DAILY_MINUTES,
    )
    remainder = new_total_minutes - per_day * len(incomplete_days)
    for i, dp in enumerate(incomplete_days):
        dp.total_minutes = per_day + (1 if i < remainder else 0)

    if commit:
        db.commit()
        db.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def weekly_plan_stats(weekly_plan: WeeklyPlan) -> dict[str, Any]:
    """
    Return a statistics dictionary for a WeeklyPlan.

    Keys
    ----
    total_days, completed_days, pending_days, completion_percentage,
    total_minutes, completed_minutes, average_performance_score,
    focus_skills
    """
    daily_plans = weekly_plan.daily_plans or []
    completed_days = [dp for dp in daily_plans if dp.is_completed]
    pending_days = [dp for dp in daily_plans if not dp.is_completed]
    completed_minutes = sum(dp.total_minutes or 0 for dp in completed_days)
    scores = [
        dp.performance_score
        for dp in completed_days
        if dp.performance_score is not None
    ]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    focus_skills = list(
        {dp.focus_skill for dp in daily_plans if dp.focus_skill}
    )

    return {
        "total_days": len(daily_plans),
        "completed_days": len(completed_days),
        "pending_days": len(pending_days),
        "completion_percentage": weekly_plan.completion_percentage or 0.0,
        "total_minutes": weekly_plan.total_minutes or 0,
        "completed_minutes": completed_minutes,
        "average_performance_score": avg_score,
        "focus_skills": focus_skills,
    }


def learning_path_progress(
    learning_path_id: int, db: Session
) -> dict[str, Any]:
    """
    Aggregate progress across all WeeklyPlans for a LearningPath.

    Keys
    ----
    total_weeks, completed_weeks, current_week_number,
    overall_completion_percentage, total_minutes, completed_minutes
    """
    plans = list_weekly_plans(learning_path_id, db)
    if not plans:
        return {
            "total_weeks": 0,
            "completed_weeks": 0,
            "current_week_number": None,
            "overall_completion_percentage": 0.0,
            "total_minutes": 0,
            "completed_minutes": 0,
        }

    completed_weeks = [p for p in plans if p.is_completed]
    current = next((p for p in plans if not p.is_completed), plans[-1])
    total_min = sum(p.total_minutes or 0 for p in plans)
    completed_min = sum(p.total_minutes or 0 for p in completed_weeks)
    overall_pct = round(len(completed_weeks) / len(plans) * 100, 2)

    return {
        "total_weeks": len(plans),
        "completed_weeks": len(completed_weeks),
        "current_week_number": current.week_number,
        "overall_completion_percentage": overall_pct,
        "total_minutes": total_min,
        "completed_minutes": completed_min,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_or_raise(weekly_plan_id: int, db: Session) -> WeeklyPlan:
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == weekly_plan_id).first()
    if plan is None:
        raise ValueError(f"WeeklyPlan {weekly_plan_id} not found.")
    return plan


def _hours_to_minutes(hours: float | None) -> int:
    if hours is None:
        return DEFAULT_MINUTES_PER_WEEK
    return max(MIN_DAILY_MINUTES, int(hours * 60))


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _resolve_week_start(
    learning_path: LearningPath,
    week_number: int,
    override: date | None,
) -> date | None:
    if override is not None:
        return override
    if learning_path.started_at is not None:
        started: date = (
            learning_path.started_at.date()
            if isinstance(learning_path.started_at, datetime)
            else learning_path.started_at
        )
        return started + timedelta(weeks=week_number - 1)
    return None


def _pick_subtopics_for_week(
    learning_path: LearningPath,
    week_number: int,
    db: Session,
) -> list[int]:
    """
    Return a list of subtopic IDs appropriate for *week_number* by evenly
    distributing the learning path's subtopics across its total weeks.

    Falls back to an empty list when no subtopics are available.
    """
    # Attempt to derive subtopics from existing weekly plans first
    existing: WeeklyPlan | None = (
        db.query(WeeklyPlan)
        .filter(
            WeeklyPlan.learning_path_id == learning_path.id,
            WeeklyPlan.week_number == week_number,
        )
        .first()
    )
    if existing and existing.subtopic_ids:
        return list(existing.subtopic_ids)

    # Derive from current_level / target_level
    from app.models.syllabus import SyllabusLevel, SyllabusTopic  # local import to avoid circulars

    CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
    try:
        start_idx = CEFR_LEVELS.index(learning_path.current_level)
        end_idx = CEFR_LEVELS.index(learning_path.target_level)
    except (ValueError, AttributeError):
        return []

    levels_between = CEFR_LEVELS[start_idx : end_idx + 1]
    level_rows = (
        db.query(SyllabusLevel)
        .filter(SyllabusLevel.code.in_(levels_between))
        .all()
    )
    level_ids = [lv.id for lv in level_rows]
    if not level_ids:
        return []

    subtopics = (
        db.query(SyllabusSubtopic)
        .join(SyllabusTopic, SyllabusSubtopic.topic_id == SyllabusTopic.id)
        .filter(SyllabusTopic.level_id.in_(level_ids))
        .order_by(SyllabusSubtopic.id)
        .all()
    )
    if not subtopics:
        return []

    total_weeks = max(learning_path.total_weeks or 1, 1)
    chunk = max(1, len(subtopics) // total_weeks)
    offset = (week_number - 1) * chunk
    week_subtopics = subtopics[offset : offset + chunk]
    return [s.id for s in week_subtopics]


def _derive_focus_topics(subtopic_ids: list[int], db: Session) -> list[str]:
    """Return topic names for the given subtopic IDs (deduplicated, ordered)."""
    if not subtopic_ids:
        return []
    subtopics = (
        db.query(SyllabusSubtopic)
        .filter(SyllabusSubtopic.id.in_(subtopic_ids))
        .all()
    )
    seen: set[str] = set()
    topics: list[str] = []
    for st in subtopics:
        name = st.topic.name if st.topic else st.name
        if name not in seen:
            seen.add(name)
            topics.append(name)
    return topics


def _build_goals(focus_topics: list[str], target_level: str) -> list[str]:
    goals: list[str] = []
    if focus_topics:
        goals.append(f"Master key concepts in: {', '.join(focus_topics[:3])}.")
    goals.append(f"Progress toward {target_level} proficiency.")
    goals.append("Complete all daily exercises and review sessions.")
    return goals


def _build_daily_plans(
    weekly_plan: WeeklyPlan,
    total_minutes: int,
    subtopic_ids: list[int],
    focus_skill: str | None,
    week_start: date | None,
) -> list[DailyPlan]:
    """Create DAYS_PER_WEEK DailyPlan objects for the given WeeklyPlan."""
    per_day_base = _clamp(
        total_minutes // DAYS_PER_WEEK, MIN_DAILY_MINUTES, MAX_DAILY_MINUTES
    )
    remainder = total_minutes - per_day_base * DAYS_PER_WEEK

    # Spread subtopics across days
    chunks = _split_list(subtopic_ids, DAYS_PER_WEEK)

    daily_plans: list[DailyPlan] = []
    for day_idx in range(DAYS_PER_WEEK):
        day_number = day_idx + 1
        skill = focus_skill or SKILL_ROTATION[day_idx % len(SKILL_ROTATION)]
        day_minutes = per_day_base + (1 if day_idx < remainder else 0)
        scheduled: date | None = (
            week_start + timedelta(days=day_idx) if week_start else None
        )
        dp = DailyPlan(
            weekly_plan_id=weekly_plan.id,
            day_number=day_number,
            title=f"Day {day_number} – {skill.capitalize()}",
            description=(
                f"Day {day_number} practice: focus on {skill}. "
                f"Target {day_minutes} minutes of active study."
            ),
            focus_skill=skill,
            subtopic_ids=chunks[day_idx] if day_idx < len(chunks) else [],
            exercise_ids=[],
            total_minutes=day_minutes,
            is_completed=False,
            completion_percentage=0.0,
            scheduled_date=scheduled,
        )
        daily_plans.append(dp)
    return daily_plans


def _split_list(lst: list[Any], n: int) -> list[list[Any]]:
    """Split *lst* into *n* roughly equal chunks."""
    if not lst:
        return [[] for _ in range(n)]
    k, rem = divmod(len(lst), n)
    chunks: list[list[Any]] = []
    start = 0
    for i in range(n):
        end = start + k + (1 if i < rem else 0)
        chunks.append(lst[start:end])
        start = end
    return chunks


def _maybe_complete_learning_path(plan: WeeklyPlan, db: Session) -> None:
    """Mark the parent LearningPath completed if all its weeks are done."""
    lp: LearningPath | None = (
        db.query(LearningPath)
        .filter(LearningPath.id == plan.learning_path_id)
        .first()
    )
    if lp is None:
        return
    all_plans = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.learning_path_id == lp.id)
        .all()
    )
    if all_plans and all(p.is_completed for p in all_plans):
        lp.is_completed = True
        lp.completed_at = lp.completed_at or datetime.utcnow()
        logger.info("LearningPath %d marked as completed.", lp.id)
