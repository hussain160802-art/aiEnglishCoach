from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.exercise import DifficultyLevel, ExerciseType, SkillType


# ---------------------------------------------------------------------------
# Exercise schemas
# ---------------------------------------------------------------------------


class ExerciseCreate(BaseModel):
    daily_plan_id: Optional[int] = None
    subtopic_id: Optional[int] = None
    exercise_type: ExerciseType
    skill: SkillType
    difficulty: DifficultyLevel
    cefr_level: str = Field(..., description="CEFR level code, e.g. A1, B2")
    title: str
    instructions: str
    content: dict[str, Any]
    hints: Optional[list[str]] = None
    explanation: Optional[str] = None
    example_answer: Optional[str] = None
    tags: Optional[list[str]] = None
    learning_objectives: Optional[list[str]] = None
    estimated_minutes: int = Field(default=10, ge=1)
    max_score: float = Field(default=100.0, ge=0)
    passing_score: float = Field(default=60.0, ge=0)
    is_active: bool = True
    is_ai_generated: bool = False
    generation_prompt: Optional[str] = None
    source_reference: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def validate_cefr_level(self) -> "ExerciseCreate":
        valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}
        if self.cefr_level not in valid_levels:
            raise ValueError(
                f"cefr_level must be one of {sorted(valid_levels)}, got '{self.cefr_level}'"
            )
        return self

    @model_validator(mode="after")
    def validate_passing_score(self) -> "ExerciseCreate":
        if self.passing_score > self.max_score:
            raise ValueError("passing_score cannot exceed max_score")
        return self


class ExerciseUpdate(BaseModel):
    exercise_type: Optional[ExerciseType] = None
    skill: Optional[SkillType] = None
    difficulty: Optional[DifficultyLevel] = None
    cefr_level: Optional[str] = None
    title: Optional[str] = None
    instructions: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    hints: Optional[list[str]] = None
    explanation: Optional[str] = None
    example_answer: Optional[str] = None
    tags: Optional[list[str]] = None
    learning_objectives: Optional[list[str]] = None
    estimated_minutes: Optional[int] = Field(default=None, ge=1)
    max_score: Optional[float] = Field(default=None, ge=0)
    passing_score: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    source_reference: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def validate_cefr_level(self) -> "ExerciseUpdate":
        if self.cefr_level is not None:
            valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}
            if self.cefr_level not in valid_levels:
                raise ValueError(
                    f"cefr_level must be one of {sorted(valid_levels)}, got '{self.cefr_level}'"
                )
        return self

    @model_validator(mode="after")
    def validate_passing_score(self) -> "ExerciseUpdate":
        if self.passing_score is not None and self.max_score is not None:
            if self.passing_score > self.max_score:
                raise ValueError("passing_score cannot exceed max_score")
        return self


class ExerciseResponse(BaseModel):
    id: int
    daily_plan_id: Optional[int] = None
    subtopic_id: Optional[int] = None
    exercise_type: ExerciseType
    skill: SkillType
    difficulty: DifficultyLevel
    cefr_level: str
    title: str
    instructions: str
    content: dict[str, Any]
    hints: Optional[list[str]] = None
    explanation: Optional[str] = None
    example_answer: Optional[str] = None
    tags: Optional[list[str]] = None
    learning_objectives: Optional[list[str]] = None
    estimated_minutes: int
    max_score: float
    passing_score: float
    is_active: bool
    is_ai_generated: bool
    generation_prompt: Optional[str] = None
    source_reference: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExerciseSummary(BaseModel):
    id: int
    daily_plan_id: Optional[int] = None
    exercise_type: ExerciseType
    skill: SkillType
    difficulty: DifficultyLevel
    cefr_level: str
    title: str
    estimated_minutes: int
    is_active: bool
    is_ai_generated: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Exercise generation / AI request schemas
# ---------------------------------------------------------------------------


class ExerciseGenerateRequest(BaseModel):
    daily_plan_id: Optional[int] = None
    subtopic_id: Optional[int] = None
    exercise_type: ExerciseType
    skill: SkillType
    difficulty: DifficultyLevel
    cefr_level: str = Field(..., description="CEFR level code, e.g. A1, B2")
    topic: str = Field(..., description="Topic or theme for the exercise")
    learning_objectives: Optional[list[str]] = None
    estimated_minutes: int = Field(default=10, ge=1)
    additional_instructions: Optional[str] = None
    count: int = Field(default=1, ge=1, le=20, description="Number of exercises to generate")

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def validate_cefr_level(self) -> "ExerciseGenerateRequest":
        valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}
        if self.cefr_level not in valid_levels:
            raise ValueError(
                f"cefr_level must be one of {sorted(valid_levels)}, got '{self.cefr_level}'"
            )
        return self


# ---------------------------------------------------------------------------
# ExerciseAttempt schemas
# ---------------------------------------------------------------------------


class ExerciseAttemptCreate(BaseModel):
    exercise_id: int
    user_id: int
    daily_plan_id: Optional[int] = None
    user_answer: Any
    time_spent_seconds: Optional[int] = Field(default=None, ge=0)

    model_config = {"from_attributes": True}


class ExerciseAttemptUpdate(BaseModel):
    is_correct: Optional[bool] = None
    score: Optional[float] = Field(default=None, ge=0)
    feedback: Optional[str] = None
    ai_feedback: Optional[str] = None
    error_analysis: Optional[dict[str, Any]] = None
    improvement_notes: Optional[str] = None
    is_completed: Optional[bool] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExerciseAttemptResponse(BaseModel):
    id: int
    exercise_id: int
    user_id: int
    daily_plan_id: Optional[int] = None
    user_answer: Any
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    time_spent_seconds: Optional[int] = None
    feedback: Optional[str] = None
    ai_feedback: Optional[str] = None
    error_analysis: Optional[dict[str, Any]] = None
    improvement_notes: Optional[str] = None
    attempt_number: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExerciseAttemptSummary(BaseModel):
    id: int
    exercise_id: int
    user_id: int
    is_correct: Optional[bool] = None
    score: Optional[float] = None
    attempt_number: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Grading / feedback schemas
# ---------------------------------------------------------------------------


class GradingRequest(BaseModel):
    attempt_id: int
    exercise_id: int
    user_answer: Any
    use_ai: bool = Field(default=True, description="Whether to use AI for feedback generation")

    model_config = {"from_attributes": True}


class GradingResult(BaseModel):
    attempt_id: int
    exercise_id: int
    is_correct: bool
    score: float = Field(..., ge=0)
    feedback: str
    ai_feedback: Optional[str] = None
    error_analysis: Optional[dict[str, Any]] = None
    improvement_notes: Optional[str] = None
    correct_answer: Optional[Any] = None
    explanation: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Batch / list response helpers
# ---------------------------------------------------------------------------


class ExerciseListResponse(BaseModel):
    exercises: list[ExerciseSummary]
    total: int
    page: int = 1
    page_size: int = 20

    model_config = {"from_attributes": True}


class ExerciseAttemptListResponse(BaseModel):
    attempts: list[ExerciseAttemptSummary]
    total: int
    page: int = 1
    page_size: int = 20

    model_config = {"from_attributes": True}
