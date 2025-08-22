from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"

class ArchiveType(enum.Enum):
    ANNOUNCEMENT = "announcement"
    EVENT = "event"

class User(Base):
    """User model for authentication - supports both admin and student roles"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Announcement(Base):
    """Announcement model for department notices"""
    __tablename__ = "announcements"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Event(Base):
    """Event model for department events"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Archive(Base):
    """Archive model for storing past announcements and events"""
    __tablename__ = "archive"
    
    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)  # Reference to original item ID
    type = Column(Enum(ArchiveType), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)  # JSON string for flexible storage
    archived_at = Column(DateTime(timezone=True), server_default=func.now())