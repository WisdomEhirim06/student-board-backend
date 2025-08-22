from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"

class ArchiveType(str, Enum):
    ANNOUNCEMENT = "announcement"
    EVENT = "event"

# Authentication Schemas
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.STUDENT

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: str
    email: str
    role: UserRole
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Announcement Schemas
class AnnouncementBase(BaseModel):
    title: str
    content: str

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class AnnouncementResponse(AnnouncementBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

# Event Schemas
class EventBase(BaseModel):
    title: str
    description: str
    event_date: datetime

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[datetime] = None

class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

# Archive Schemas
class ArchiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    original_id: int
    type: ArchiveType
    title: str
    content: str
    archived_at: datetime

# Search Schemas
class SearchParams(BaseModel):
    keyword: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    content_type: Optional[str] = None  # "announcement" or "event"

class SearchResponse(BaseModel):
    announcements: List[AnnouncementResponse]
    events: List[EventResponse]
    total_results: int

# Generic Response Schemas
class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    detail: str