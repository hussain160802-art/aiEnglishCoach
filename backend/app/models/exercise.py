from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
import enum

from app.database import Base


class ExerciseType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_IN_THE_BLANK = "fill_in_the_blank"
    MATCHING = "matching"
    REORDERING = "reordering"
    FREE_WRITING = "free_writing"
    SPEAKING = "speaking"
    LISTENING = "listening"
    READING_COMPREHENSION = "reading_comprehension"
    DIALOGUE = "dialogue"
    TRANSLATION = "translation"
    ERROR_CORRECTION = "error_correction"
    VOCABULARY_BUILDER = "vocabulary_builder"


class SkillType(str, enum.Enum):
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    READING = "reading"
    LISTENING = "listening"
    SPEAKING = "speaking"
    WRITING = "writing"
    PRONUNCIATION = "pronunciation"


class DifficultyLevel(str, enum.Enum):
    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    UPPER_INTERMEDIATE = "upper_intermediate"
    ADVANCED = "advanced"
    PROFICIENT = "proficient"


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    daily_plan_id = Column(Integer, ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    subtopic_id = Column(Integer, ForeignKey("syllabus_subtopics.id", ondelete="SET NULL"), nullable=True, index=True)

    # Classification
    exercise_type = Column(Enum(ExerciseType), nullable=False, index=True)
    skill = Column(Enum(SkillType), nullable=False, index=True)
    difficulty = Column(Enum(DifficultyLevel), nullable=False, index=True)
    cefr_level = Column(String(10), nullable=True, index=True)

    # Content
    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    # content structure varies by exercise_type:
    # multiple_choice: {question, options: [str], correct_index: int}
    # fill_in_the_blank: {text_with_blanks, answers: [str]}
    # matching: {pairs: [{left, right}]}
    # reordering: {items: [str], correct_order: [int]}
    # free_writing / speaking: {prompt: str}
    # listening: {audio_url, transcript, questions: [...]}
    # reading_comprehension: {passage, questions: [...]}
    # dialogue: {scenario, turns: [{role, text}]}
    # translation: {source_text, source_language, target_language}
    # error_correction: {text_with_errors, corrections: [{original, corrected}]}
    # vocabulary_builder: {words: [{word, definition, example, pos}]}

    hints = Column(JSON, nullable=True, default=list)          # list[str]
    explanation = Column(Text, nullable=True)
    example_answer = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True, default=list)            # list[str]
    learning_objectives = Column(JSON, nullable=True, default=list)  # list[str]

    # Timing & scoring
    estimated_minutes = Column(Integer, nullable=False, default=5)
    max_score = Column(Float, nullable=False, default=100.0)
    passing_score = Column(Float, nullable=False, default=60.0)

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    is_ai_generated = Column(Boolean, nullable=False, default=True)
    generation_prompt = Column(Text, nullable=True)
    source_reference = Column(String(500), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    daily_plan = relationship("DailyPlan", back_populates="exercises")
    subtopic = relationship("SyllabusSubtopic", back_populates="exercises")
    attempts = relationship("ExerciseAttempt", back_populates="exercise", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<Exercise(id={self.id}, type={self.exercise_type}, "
            f"skill={self.skill}, difficulty={self.difficulty}, title='{self.title}')>"
        )


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    daily_plan_id = Column(Integer, ForeignKey("daily_plans.id", ondelete="SET NULL"), nullable=True, index=True)

    # Attempt data
    user_answer = Column(JSON, nullable=True)           # flexible; mirrors content structure
    is_correct = Column(Boolean, nullable=True)         # None if manually graded
    score = Column(Float, nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)

    # Feedback
    feedback = Column(Text, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    error_analysis = Column(JSON, nullable=True, default=dict)   # {error_type: count, ...}
    improvement_notes = Column(Text, nullable=True)

    # State
    attempt_number = Column(Integer, nullable=False, default=1)
    is_completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    exercise = relationship("Exercise", back_populates="attempts")
    user = relationship("User", back_populates="exercise_attempts")

    def __repr__(self) -> str:
        return (
            f"<ExerciseAttempt(id={self.id}, exercise_id={self.exercise_id}, "
            f"user_id={self.user_id}, score={self.score}, attempt={self.attempt_number})>"
        )
