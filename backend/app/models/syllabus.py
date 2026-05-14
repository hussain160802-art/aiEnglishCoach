from sqlalchemy import Column, Integer, String, Float, Text, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SyllabusLevel(Base):
    """Represents a CEFR proficiency level in the syllabus (A1, A2, B1, B2, C1, C2)."""

    __tablename__ = "syllabus_levels"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)  # e.g. "A1", "B2"
    name = Column(String(100), nullable=False)                          # e.g. "Elementary"
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)                  # sort order (1=A1 … 6=C2)
    total_hours = Column(Float, nullable=True)                          # estimated study hours
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    topics = relationship("SyllabusTopic", back_populates="level", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SyllabusLevel(id={self.id}, code='{self.code}', name='{self.name}')>"


class SyllabusTopic(Base):
    """A broad topic area within a CEFR level (e.g. Grammar, Vocabulary, Speaking)."""

    __tablename__ = "syllabus_topics"

    id = Column(Integer, primary_key=True, index=True)
    level_id = Column(Integer, ForeignKey("syllabus_levels.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)   # e.g. "grammar", "vocabulary", "skills"
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    level = relationship("SyllabusLevel", back_populates="topics")
    subtopics = relationship("SyllabusSubtopic", back_populates="topic", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SyllabusTopic(id={self.id}, name='{self.name}', level_id={self.level_id})>"


class SyllabusSubtopic(Base):
    """A specific subtopic or learning objective within a SyllabusTopic."""

    __tablename__ = "syllabus_subtopics"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    learning_objectives = Column(JSON, nullable=True)   # list[str] of measurable objectives
    keywords = Column(JSON, nullable=True)              # list[str] of key terms / vocabulary
    example_sentences = Column(JSON, nullable=True)     # list[str] of usage examples
    difficulty_score = Column(Float, nullable=True)     # 0.0 – 1.0 relative difficulty
    estimated_minutes = Column(Integer, nullable=True)  # average time to cover this subtopic
    order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    topic = relationship("SyllabusTopic", back_populates="subtopics")

    def __repr__(self) -> str:
        return (
            f"<SyllabusSubtopic(id={self.id}, name='{self.name}', topic_id={self.topic_id})>"
        )
