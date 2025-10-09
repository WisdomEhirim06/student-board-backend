from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List, Optional
import os
import json

# Import models and schemas
from models import Base, User, Announcement, Event, Archive, UserRole, ArchiveType
from schemas import (
    UserLogin, UserCreate, UserResponse, Token, TokenData,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
    EventCreate, EventUpdate, EventResponse,
    ArchiveResponse, SearchParams, SearchResponse,
    MessageResponse, ErrorResponse
)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./student_board.db")

# Handle PostgreSQL URL format for Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Password hashing
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# FastAPI app
app = FastAPI(
    title="Departmental Student Information Board API",
    description="Backend API for university department notice board",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions
def verify_password(plain_password, hashed_password):
    """Verify a plain password against its hash"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
        )

def get_password_hash(password):
    """Generate password hash"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, username: str, password: str):
    """Authenticate user credentials"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

def get_admin_user(current_user: User = Depends(get_current_user)):
    """Ensure current user is admin"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires admin privileges"
        )
    return current_user

def archive_item(db: Session, item, item_type: ArchiveType):
    """Archive an announcement or event"""
    content_data = {
        "title": item.title,
        "content": item.content if hasattr(item, 'content') else item.description,
        "created_at": item.created_at.isoformat(),
        "event_date": item.event_date.isoformat() if hasattr(item, 'event_date') else None
    }
    
    archive_entry = Archive(
        original_id=item.id,
        type=item_type,
        title=item.title,
        content=json.dumps(content_data)
    )
    db.add(archive_entry)
    db.commit()

# Initialize admin user on startup
@app.on_event("startup")
async def startup_event():
    """Create default admin user if none exists"""
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_exists:
            admin_user = User(
                username="admin",
                email="admin@department.edu",
                hashed_password=get_password_hash("admin123"),  # Change in production
                role=UserRole.ADMIN
            )
            db.add(admin_user)
            db.commit()
            print("Default admin user created: admin/admin123")
    finally:
        db.close()

# Routes

# Root endpoint
@app.get("/", response_model=MessageResponse)
async def root():
    """Root endpoint with API information"""
    return {"message": "Departmental Student Information Board API is running"}

# Authentication endpoints
@app.post("/auth/login", response_model=Token)
async def login_for_access_token(user_data: UserLogin, db: Session = Depends(get_db)):
    """Admin login endpoint"""
    user = authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

# Announcement endpoints
@app.get("/announcements/", response_model=List[AnnouncementResponse])
async def get_announcements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all announcements (public endpoint)"""
    announcements = db.query(Announcement).offset(skip).limit(limit).all()
    return announcements

@app.get("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(announcement_id: int, db: Session = Depends(get_db)):
    """Get specific announcement (public endpoint)"""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return announcement

@app.post("/announcements/", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    announcement: AnnouncementCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create new announcement (admin only)"""
    db_announcement = Announcement(**announcement.dict())
    db.add(db_announcement)
    db.commit()
    db.refresh(db_announcement)
    return db_announcement

@app.put("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: int,
    announcement_update: AnnouncementUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update announcement (admin only)"""
    db_announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if db_announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    update_data = announcement_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_announcement, field, value)
    
    db.commit()
    db.refresh(db_announcement)
    return db_announcement

@app.delete("/announcements/{announcement_id}", response_model=MessageResponse)
async def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete announcement and archive it (admin only)"""
    db_announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if db_announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Archive before deletion
    archive_item(db, db_announcement, ArchiveType.ANNOUNCEMENT)
    
    db.delete(db_announcement)
    db.commit()
    return {"message": "Announcement deleted and archived successfully"}

# Event endpoints
@app.get("/events/", response_model=List[EventResponse])
async def get_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all events (public endpoint)"""
    events = db.query(Event).offset(skip).limit(limit).all()
    return events

@app.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    """Get specific event (public endpoint)"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@app.post("/events/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create new event (admin only)"""
    db_event = Event(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Update event (admin only)"""
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    update_data = event_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)
    
    db.commit()
    db.refresh(db_event)
    return db_event

@app.delete("/events/{event_id}", response_model=MessageResponse)
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete event and archive it (admin only)"""
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Archive before deletion
    archive_item(db, db_event, ArchiveType.EVENT)
    
    db.delete(db_event)
    db.commit()
    return {"message": "Event deleted and archived successfully"}

# Archive endpoints
@app.get("/archive/", response_model=List[ArchiveResponse])
async def get_archive(
    skip: int = 0, 
    limit: int = 100,
    archive_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get archived items (public endpoint)"""
    query = db.query(Archive)
    
    if archive_type and archive_type in ["announcement", "event"]:
        query = query.filter(Archive.type == ArchiveType(archive_type))
    
    archived_items = query.offset(skip).limit(limit).all()
    return archived_items

# Search endpoints
@app.post("/search/", response_model=SearchResponse)
async def search_content(search_params: SearchParams, db: Session = Depends(get_db)):
    """Search announcements and events (public endpoint)"""
    announcements_query = db.query(Announcement)
    events_query = db.query(Event)
    
    # Apply keyword search
    if search_params.keyword:
        keyword = f"%{search_params.keyword}%"
        announcements_query = announcements_query.filter(
            or_(
                Announcement.title.ilike(keyword),
                Announcement.content.ilike(keyword)
            )
        )
        events_query = events_query.filter(
            or_(
                Event.title.ilike(keyword),
                Event.description.ilike(keyword)
            )
        )
    
    # Apply date range filter
    if search_params.start_date:
        announcements_query = announcements_query.filter(
            Announcement.created_at >= search_params.start_date
        )
        events_query = events_query.filter(
            Event.created_at >= search_params.start_date
        )
    
    if search_params.end_date:
        announcements_query = announcements_query.filter(
            Announcement.created_at <= search_params.end_date
        )
        events_query = events_query.filter(
            Event.created_at <= search_params.end_date
        )
    
    # Filter by content type
    announcements = []
    events = []
    
    if not search_params.content_type or search_params.content_type == "announcement":
        announcements = announcements_query.all()
    
    if not search_params.content_type or search_params.content_type == "event":
        events = events_query.all()
    
    total_results = len(announcements) + len(events)
    
    return SearchResponse(
        announcements=announcements,
        events=events,
        total_results=total_results
    )

# Health check endpoint
@app.get("/health", response_model=MessageResponse)
async def health_check():
    """Health check endpoint"""
    return {"message": "API is healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)