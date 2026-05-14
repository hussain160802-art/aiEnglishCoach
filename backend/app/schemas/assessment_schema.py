from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Assessment Request / Input schemas
# ---------------------------------------------------------------------------

class AssessmentCreate(BaseModel):
    """Payload sent by the client to create a new assessment."""

    user_id: int = Field(..., gt=0, description="ID of the user being assessed")
    raw_responses: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw question-answer pairs from the placement quiz",
    )
    writing_sample: Optional[str] = Field(
        default=None,
        max_length=10_000,
        description="Free-text writing sample submitted by the user",
    )
    speaking_sample_url: Optional[str] = Field(
        default=None,
        description="URL pointing to an uploaded audio/video speaking sample",
    )

    model_config = {"from_attributes": True}


class AssessmentUpdate(BaseModel):
    """Partial update for an existing assessment (e.g. after AI analysis)."""

    grammar_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    vocabulary_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reading_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    listening_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    speaking_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    writing_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    detected_level: Optional[str] = Field(
        default=None,
        description="CEFR level detected by the analyser (A1–C2)",
    )
    strengths: Optional[List[str]] = Field(default=None)
    weaknesses: Optional[List[str]] = Field(default=None)
    recommendations: Optional[List[str]] = Field(default=None)
    analysis_notes: Optional[str] = Field(default=None, max_length=5_000)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Score sub-schema (reusable read fragment)
# ---------------------------------------------------------------------------

class SkillScores(BaseModel):
    """Breakdown of individual skill scores returned in read responses."""

    grammar: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    vocabulary: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reading: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    listening: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    speaking: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    writing: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    overall: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assessment Response / Output schemas
# ---------------------------------------------------------------------------

class AssessmentResponse(BaseModel):
    """Full assessment record returned to the client."""

    id: int
    user_id: int

    # Raw inputs (may be omitted in list views)
    raw_responses: Optional[Dict[str, Any]] = None
    writing_sample: Optional[str] = None
    speaking_sample_url: Optional[str] = None

    # Scores
    grammar_score: Optional[float] = None
    vocabulary_score: Optional[float] = None
    reading_score: Optional[float] = None
    listening_score: Optional[float] = None
    speaking_score: Optional[float] = None
    writing_score: Optional[float] = None
    overall_score: Optional[float] = None

    # Analysis results
    detected_level: Optional[str] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
    analysis_notes: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @property
    def skill_scores(self) -> SkillScores:
        """Convenience accessor returning scores as a structured object."""
        return SkillScores(
            grammar=self.grammar_score,
            vocabulary=self.vocabulary_score,
            reading=self.reading_score,
            listening=self.listening_score,
            speaking=self.speaking_score,
            writing=self.writing_score,
            overall=self.overall_score,
        )


class AssessmentSummary(BaseModel):
    """Lightweight assessment record used in list endpoints."""

    id: int
    user_id: int
    overall_score: Optional[float] = None
    detected_level: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analysis request / result schemas (used by assessment_analyzer service)
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    """Input payload sent to the AI analyser service."""

    assessment_id: int = Field(..., gt=0)
    raw_responses: Optional[Dict[str, Any]] = None
    writing_sample: Optional[str] = None
    speaking_sample_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AnalysisResult(BaseModel):
    """Output produced by the AI analyser service."""

    detected_level: str = Field(
        ...,
        description="CEFR level string, e.g. 'B1' or 'B2'",
    )
    grammar_score: float = Field(..., ge=0.0, le=100.0)
    vocabulary_score: float = Field(..., ge=0.0, le=100.0)
    reading_score: float = Field(..., ge=0.0, le=100.0)
    listening_score: float = Field(..., ge=0.0, le=100.0)
    speaking_score: float = Field(..., ge=0.0, le=100.0)
    writing_score: float = Field(..., ge=0.0, le=100.0)
    overall_score: float = Field(..., ge=0.0, le=100.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    analysis_notes: Optional[str] = None

    @field_validator("detected_level")
    @classmethod
    def validate_cefr_level(cls, value: str) -> str:
        allowed = {"A1", "A2", "B1", "B2", "C1", "C2"}
        normalised = value.strip().upper()
        if normalised not in allowed:
            raise ValueError(
                f"detected_level must be one of {sorted(allowed)}, got '{value}'"
            )
        return normalised

    model_config = {"from_attributes": True}
