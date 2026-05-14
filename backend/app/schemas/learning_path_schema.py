from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────
# DailyPlan schemas
# ─────────────────────────────────────────────

class DailyPlanCreate(BaseModel):
    weekly_plan_id: int
    day_number: int = Field(..., ge=1, le=7)
    title: str
    description: Optional[str] = None
    focus_skill: Optional[str] = None
    subtopic_ids: List[int] = Field(default_factory=list)
    exercise_ids: List[int] = Field(default_factory=list)
    total_minutes: int = Field(default=0, ge=0)
    scheduled_date: Optional[datetime] = None


class DailyPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    focus_skill: Optional[str] = None
    subtopic_ids: Optional[List[int]] = None
    exercise_ids: Optional[List[int]] = None
    total_minutes: Optional[int] = Field(default=None, ge=0)
    is_completed: Optional[bool] = None
    completion_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    performance_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    notes: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DailyPlanResponse(BaseModel):
    id: int
    weekly_plan_id: int
    day_number: int
    title: str
    description: Optional[str] = None
    focus_skill: Optional[str] = None
    subtopic_ids: List[int] = Field(default_factory=list)
    exercise_ids: List[int] = Field(default_factory=list)
    total_minutes: int
    is_completed: bool
    completion_percentage: float
    performance_score: Optional[float] = None
    notes: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DailyPlanSummary(BaseModel):
    id: int
    weekly_plan_id: int
    day_number: int
    title: str
    focus_skill: Optional[str] = None
    total_minutes: int
    is_completed: bool
    completion_percentage: float
    scheduled_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# WeeklyPlan schemas
# ─────────────────────────────────────────────

class WeeklyPlanCreate(BaseModel):
    learning_path_id: int
    week_number: int = Field(..., ge=1)
    title: str
    description: Optional[str] = None
    focus_topics: List[str] = Field(default_factory=list)
    subtopic_ids: List[int] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    total_minutes: int = Field(default=0, ge=0)


class WeeklyPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    focus_topics: Optional[List[str]] = None
    subtopic_ids: Optional[List[int]] = None
    goals: Optional[List[str]] = None
    total_minutes: Optional[int] = Field(default=None, ge=0)
    is_completed: Optional[bool] = None
    completion_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WeeklyPlanResponse(BaseModel):
    id: int
    learning_path_id: int
    week_number: int
    title: str
    description: Optional[str] = None
    focus_topics: List[str] = Field(default_factory=list)
    subtopic_ids: List[int] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    total_minutes: int
    is_completed: bool
    completion_percentage: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    daily_plans: List[DailyPlanSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WeeklyPlanSummary(BaseModel):
    id: int
    learning_path_id: int
    week_number: int
    title: str
    total_minutes: int
    is_completed: bool
    completion_percentage: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# LearningPath schemas
# ─────────────────────────────────────────────

_VALID_CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}


class LearningPathCreate(BaseModel):
    user_id: int
    assessment_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    target_level: str
    current_level: str
    total_weeks: int = Field(..., ge=1)
    hours_per_week: float = Field(..., gt=0)
    focus_areas: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cefr_levels(self) -> "LearningPathCreate":
        if self.target_level not in _VALID_CEFR_LEVELS:
            raise ValueError(
                f"target_level must be one of {sorted(_VALID_CEFR_LEVELS)}, "
                f"got '{self.target_level}'"
            )
        if self.current_level not in _VALID_CEFR_LEVELS:
            raise ValueError(
                f"current_level must be one of {sorted(_VALID_CEFR_LEVELS)}, "
                f"got '{self.current_level}'"
            )
        return self


class LearningPathUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_level: Optional[str] = None
    current_level: Optional[str] = None
    total_weeks: Optional[int] = Field(default=None, ge=1)
    hours_per_week: Optional[float] = Field(default=None, gt=0)
    focus_areas: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_completed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_cefr_levels(self) -> "LearningPathUpdate":
        for field_name in ("target_level", "current_level"):
            value = getattr(self, field_name)
            if value is not None and value not in _VALID_CEFR_LEVELS:
                raise ValueError(
                    f"{field_name} must be one of {sorted(_VALID_CEFR_LEVELS)}, "
                    f"got '{value}'"
                )
        return self


class LearningPathResponse(BaseModel):
    id: int
    user_id: int
    assessment_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    target_level: str
    current_level: str
    total_weeks: int
    hours_per_week: float
    focus_areas: List[str] = Field(default_factory=list)
    is_active: bool
    is_completed: bool
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    weekly_plans: List[WeeklyPlanSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class LearningPathSummary(BaseModel):
    id: int
    user_id: int
    title: str
    target_level: str
    current_level: str
    total_weeks: int
    hours_per_week: float
    is_active: bool
    is_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Generation request / result schemas
# ─────────────────────────────────────────────

class LearningPathGenerateRequest(BaseModel):
    user_id: int
    assessment_id: int
    target_level: str
    hours_per_week: float = Field(..., gt=0)
    focus_areas: List[str] = Field(default_factory=list)
    total_weeks: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target_level(self) -> "LearningPathGenerateRequest":
        if self.target_level not in _VALID_CEFR_LEVELS:
            raise ValueError(
                f"target_level must be one of {sorted(_VALID_CEFR_LEVELS)}, "
                f"got '{self.target_level}'"
            )
        return self


class WeeklyPlanGenerateRequest(BaseModel):
    learning_path_id: int
    week_number: int = Field(..., ge=1)
    hours_available: float = Field(..., gt=0)
    focus_skill: Optional[str] = None


class DailyPlanGenerateRequest(BaseModel):
    weekly_plan_id: int
    day_number: int = Field(..., ge=1, le=7)
    minutes_available: int = Field(..., gt=0)
    focus_skill: Optional[str] = None


class ProgressUpdate(BaseModel):
    entity: str = Field(..., description="One of: learning_path, weekly_plan, daily_plan")
    entity_id: int
    is_completed: bool
    completion_percentage: float = Field(..., ge=0.0, le=100.0)
    performance_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    notes: Optional[str] = None
