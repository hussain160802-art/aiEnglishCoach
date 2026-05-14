from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Assessment input
    raw_responses = Column(JSON, nullable=True)  # Raw answers from the user
    writing_sample = Column(Text, nullable=True)  # Free-form writing sample
    speaking_sample_url = Column(String(512), nullable=True)  # Optional audio URL

    # Skill scores (0.0 – 10.0 scale)
    grammar_score = Column(Float, nullable=True)
    vocabulary_score = Column(Float, nullable=True)
    reading_score = Column(Float, nullable=True)
    listening_score = Column(Float, nullable=True)
    speaking_score = Column(Float, nullable=True)
    writing_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)

    # Derived metadata
    detected_level = Column(String(20), nullable=True)   # e.g. "A1", "B2", "C1"
    strengths = Column(JSON, nullable=True)               # List[str]
    weaknesses = Column(JSON, nullable=True)              # List[str]
    recommendations = Column(JSON, nullable=True)         # List[str]
    analysis_notes = Column(Text, nullable=True)          # Free-form AI notes

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="assessments")

    def __repr__(self) -> str:
        return (
            f"<Assessment id={self.id} user_id={self.user_id} "
            f"level={self.detected_level!r} overall={self.overall_score}>"
        )
