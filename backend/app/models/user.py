from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    native_language = Column(String, nullable=True)
    english_level = Column(String, nullable=True)  # e.g. A1, A2, B1, B2, C1, C2
    goals = Column(JSON, nullable=True)             # list of learning goals
    preferences = Column(JSON, nullable=True)       # user preferences dict
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} level={self.english_level!r}>"
