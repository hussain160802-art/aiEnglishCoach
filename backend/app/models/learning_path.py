from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_level = Column(String(10), nullable=False)  # CEFR level code e.g. B1
    current_level = Column(String(10), nullable=False)  # CEFR level code at path creation
    total_weeks = Column(Integer, nullable=False, default=12)
    hours_per_week = Column(Float, nullable=False, default=5.0)
    focus_areas = Column(JSON, nullable=True)          # list[str] e.g. ["grammar", "speaking"]
    is_active = Column(Boolean, nullable=False, default=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="learning_paths")
    assessment = relationship("Assessment", back_populates="learning_paths")
    weekly_plans = relationship("WeeklyPlan", back_populates="learning_path", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<LearningPath id={self.id} user_id={self.user_id} "
            f"target_level={self.target_level!r} is_active={self.is_active}>"
        )


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id = Column(Integer, primary_key=True, index=True)
    learning_path_id = Column(Integer, ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    week_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    focus_topics = Column(JSON, nullable=True)          # list[str] topic names for this week
    subtopic_ids = Column(JSON, nullable=True)          # list[int] SyllabusSubtopic ids
    goals = Column(JSON, nullable=True)                 # list[str] learning goals
    total_minutes = Column(Integer, nullable=False, default=0)
    is_completed = Column(Boolean, nullable=False, default=False)
    completion_percentage = Column(Float, nullable=False, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    learning_path = relationship("LearningPath", back_populates="weekly_plans")
    daily_plans = relationship("DailyPlan", back_populates="weekly_plan", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<WeeklyPlan id={self.id} learning_path_id={self.learning_path_id} "
            f"week_number={self.week_number} is_completed={self.is_completed}>"
        )


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id = Column(Integer, primary_key=True, index=True)
    weekly_plan_id = Column(Integer, ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)        # 1–7 within the week
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    focus_skill = Column(String(50), nullable=True)     # e.g. "grammar", "vocabulary", "speaking"
    subtopic_ids = Column(JSON, nullable=True)          # list[int] SyllabusSubtopic ids
    exercise_ids = Column(JSON, nullable=True)          # list[int] Exercise ids
    total_minutes = Column(Integer, nullable=False, default=0)
    is_completed = Column(Boolean, nullable=False, default=False)
    completion_percentage = Column(Float, nullable=False, default=0.0)
    performance_score = Column(Float, nullable=True)    # 0.0–1.0 aggregate score after completion
    notes = Column(Text, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    weekly_plan = relationship("WeeklyPlan", back_populates="daily_plans")
    exercises = relationship("Exercise", back_populates="daily_plan", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<DailyPlan id={self.id} weekly_plan_id={self.weekly_plan_id} "
            f"day_number={self.day_number} is_completed={self.is_completed}>"
        )
