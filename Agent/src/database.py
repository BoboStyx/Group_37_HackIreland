"""
Database models and interactions for the AI agent system.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os
import json

from sqlalchemy import create_engine, Column, Integer, String, Text, event, DateTime
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from server_config import db_config, server_config

# Create database engine based on environment
engine = create_engine(
    db_config.get_url(server_config.environment),
    pool_size=20,
    max_overflow=0,
    pool_timeout=30,
    pool_recycle=1800
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass

@contextmanager
def get_db() -> Session:
    """Get database session with proper error handling."""
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        raise DatabaseError(f"Database error: {str(e)}")
    finally:
        db.close()

# Add event listeners for connection pool management
@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    connection_record.info['pid'] = os.getpid()

@event.listens_for(engine, "checkout")
def checkout(dbapi_connection, connection_record, connection_proxy):
    pid = os.getpid()
    if connection_record.info['pid'] != pid:
        connection_record.connection = connection_proxy.connection = None
        raise exc.DisconnectionError(
            "Connection record belongs to pid %s, attempting to check out in pid %s" %
            (connection_record.info['pid'], pid)
        )

class Conversation(Base):
    """Model for storing conversation history."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_input = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    model_used = Column(String(50), nullable=False, default="gpt-4")  # Default to GPT-4
    timestamp = Column(DATETIME(fsp=6), default=datetime.utcnow)
    meta_data = Column(Text, nullable=True)

class AgentTask(Base):
    """Model for storing agent tasks and their status."""
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DATETIME(fsp=6), default=datetime.utcnow)
    completed_at = Column(DATETIME(fsp=6), nullable=True)
    result = Column(Text, nullable=True)

class Task(Base):
    """Model for storing user tasks."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    urgency = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    alertAt = Column(DATETIME(fsp=6), nullable=True)

class Event(Base):
    """Model for storing calendar events."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DATETIME(fsp=6), nullable=False)
    end_time = Column(DATETIME(fsp=6), nullable=True)
    location = Column(String(255), nullable=True)
    participants = Column(Text, nullable=True)  # JSON array of participants
    source = Column(String(255), nullable=True)  # Where the event was detected from
    source_link = Column(String(512), nullable=True)  # Link to original source (e.g., email)
    created_at = Column(DATETIME(fsp=6), default=datetime.utcnow)
    updated_at = Column(DATETIME(fsp=6), default=datetime.utcnow, onupdate=datetime.utcnow)

class UserProfile(Base):
    """Model for storing user profiles."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DATETIME(fsp=6), default=datetime.utcnow)
    updated_at = Column(DATETIME(fsp=6), default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_input = Column(Text, nullable=False)
    structured_profile = Column(Text, nullable=False)  # JSON string of the profile

class GmailCredentials(Base):
    """Model for storing Gmail credentials."""
    __tablename__ = "gmail_credentials"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True)
    credentials = Column(Text, nullable=False)  # Encrypted credentials
    email = Column(String(255), nullable=False)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    """Initialize the database by creating all tables."""
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to initialize database: {str(e)}")

def get_tasks_by_urgency(urgency_level: int) -> List[Dict[str, Any]]:
    """
    Retrieve tasks from the database with the specified urgency.
    
    Args:
        urgency_level (int): The urgency level to filter tasks (1-5)
    
    Returns:
        List[Dict[str, Any]]: List of tasks as dictionaries
    
    Raises:
        DatabaseError: If database operation fails
        ValueError: If urgency level is invalid
    """
    if not 1 <= urgency_level <= 5:
        raise ValueError("Urgency level must be between 1 and 5")
        
    query = text("""
        SELECT id, description, urgency, status, alertAt 
        FROM tasks 
        WHERE urgency = :urgency
        ORDER BY CASE WHEN alertAt IS NULL THEN 1 ELSE 0 END, alertAt DESC
    """)
    
    try:
        with get_db() as db:
            result = db.execute(query, {"urgency": urgency_level})
            return [dict(row) for row in result]
    except DatabaseError as e:
        raise DatabaseError(f"Failed to get tasks: {str(e)}")

def update_task_status(task_id: int, status: str, alert_at: Optional[datetime] = None) -> None:
    """
    Update task status and alert time.
    
    Args:
        task_id (int): Task ID
        status (str): New status
        alert_at (Optional[datetime]): Alert time
        
    Raises:
        DatabaseError: If update fails
    """
    query = text("""
        UPDATE tasks
        SET status = :status, alertAt = :alert_at
        WHERE id = :task_id
    """)
    
    try:
        with get_db() as db:
            db.execute(query, {
                "status": status,
                "alert_at": alert_at,
                "task_id": task_id
            })
            db.commit()
    except DatabaseError as e:
        raise DatabaseError(f"Failed to update task status: {str(e)}")

def update_task_urgency(task_id: int, urgency: int) -> None:
    """
    Update the urgency level of a task.
    
    Parameters:
        task_id (int): The unique identifier of the task
        urgency (int): The new urgency level (1-5, where 5 is highest)
    
    Raises:
        ValueError: If urgency is not between 1 and 5
    """
    if not 1 <= urgency <= 5:
        raise ValueError("Urgency must be between 1 and 5")
    
    query = text("""
        UPDATE tasks
        SET urgency = :urgency
        WHERE id = :task_id
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            "urgency": urgency,
            "task_id": task_id
        })
        conn.commit()

def append_task_notes(task_id: int, notes: str) -> None:
    """
    Append additional notes/information to a task's description.
    
    Parameters:
        task_id (int): The unique identifier of the task
        notes (str): The notes to append to the task description
    """
    query = text("""
        UPDATE tasks
        SET description = CONCAT(description, '\n\nUpdate ', NOW(), ':\n', :notes)
        WHERE id = :task_id
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            "notes": notes,
            "task_id": task_id
        })
        conn.commit()

def update_task_description(task_id: int, description: str) -> None:
    """
    Update the main description of a task.
    
    Parameters:
        task_id (int): The unique identifier of the task
        description (str): The new description for the task
    """
    query = text("""
        UPDATE tasks
        SET description = :description
        WHERE id = :task_id
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            "description": description,
            "task_id": task_id
        })
        conn.commit()

def create_task(description: str, urgency: int, status: str = 'pending', alert_at: Optional[datetime] = None) -> int:
    """
    Create a new task in the database.
    
    Parameters:
        description (str): The task description
        urgency (int): The urgency level (1-5, where 5 is highest)
        status (str): The initial status (defaults to 'pending')
        alert_at (Optional[datetime]): When to alert about this task (optional)
    
    Returns:
        int: The ID of the newly created task
    
    Raises:
        ValueError: If urgency is not between 1 and 5
    """
    if not 1 <= urgency <= 5:
        raise ValueError("Urgency must be between 1 and 5")
    
    query = text("""
        INSERT INTO tasks (description, urgency, status, alertAt)
        VALUES (:description, :urgency, :status, :alert_at)
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {
            "description": description,
            "urgency": urgency,
            "status": status,
            "alert_at": alert_at
        })
        conn.commit()
        # Get the ID of the newly inserted task
        task_id = result.lastrowid
        return task_id

def get_task_by_id(task_id: int) -> Optional[Dict[str, Any]]:
    """
    Get task by ID with proper error handling.
    
    Args:
        task_id (int): Task ID
        
    Returns:
        Optional[Dict[str, Any]]: Task data or None if not found
        
    Raises:
        DatabaseError: If query fails
    """
    query = text("""
        SELECT id, description, urgency, status, alertAt 
        FROM tasks 
        WHERE id = :task_id
    """)
    
    try:
        with get_db() as db:
            result = db.execute(query, {"task_id": task_id})
            row = result.fetchone()
            return dict(row) if row else None
    except DatabaseError as e:
        raise DatabaseError(f"Failed to get task: {str(e)}")

def create_event(title: str, description: Optional[str], start_time: datetime,
                end_time: Optional[datetime] = None, location: Optional[str] = None,
                participants: Optional[List[str]] = None, source: Optional[str] = None,
                source_link: Optional[str] = None) -> int:
    """
    Create a new event in the database.
    
    Args:
        title: Event title
        description: Optional event description
        start_time: Event start time
        end_time: Optional event end time
        location: Optional event location
        participants: Optional list of participants
        source: Optional source of the event (e.g., 'email', 'manual')
        source_link: Optional link to source
        
    Returns:
        int: The ID of the newly created event
        
    Raises:
        DatabaseError: If creation fails
    """
    try:
        with get_db() as db:
            event = Event(
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=location,
                participants=json.dumps(participants) if participants else None,
                source=source,
                source_link=source_link
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return event.id
    except Exception as e:
        raise DatabaseError(f"Failed to create event: {str(e)}")

def get_events_by_timeframe(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Get events within a specific timeframe.
    
    Args:
        start: Start of timeframe
        end: End of timeframe
        
    Returns:
        List[Dict[str, Any]]: List of events
    """
    try:
        with get_db() as db:
            events = db.query(Event).filter(
                Event.start_time >= start,
                Event.start_time <= end
            ).order_by(Event.start_time).all()
            
            return [
                {
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "location": event.location,
                    "participants": json.loads(event.participants) if event.participants else None,
                    "source": event.source,
                    "source_link": event.source_link
                }
                for event in events
            ]
    except Exception as e:
        raise DatabaseError(f"Failed to get events: {str(e)}")

def update_event(event_id: int, **kwargs) -> None:
    """
    Update an event's details.
    
    Args:
        event_id: ID of event to update
        **kwargs: Fields to update
        
    Raises:
        DatabaseError: If update fails
    """
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                raise ValueError(f"Event {event_id} not found")
                
            # Handle participants separately as it needs JSON conversion
            if 'participants' in kwargs:
                kwargs['participants'] = json.dumps(kwargs['participants'])
                
            for key, value in kwargs.items():
                setattr(event, key, value)
                
            db.commit()
    except Exception as e:
        raise DatabaseError(f"Failed to update event: {str(e)}")

def delete_event(event_id: int) -> None:
    """
    Delete an event.
    
    Args:
        event_id: ID of event to delete
        
    Raises:
        DatabaseError: If deletion fails
    """
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if event:
                db.delete(event)
                db.commit()
    except Exception as e:
        raise DatabaseError(f"Failed to delete event: {str(e)}") 