"""
Database models and interactions for the AI agent system.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

from sqlalchemy import create_engine, Column, Integer, String, Text, event
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
    model_used = Column(String(50), nullable=False)
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

class UserProfile(Base):
    """Model for storing user profiles."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DATETIME(fsp=6), default=datetime.utcnow)
    updated_at = Column(DATETIME(fsp=6), default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_input = Column(Text, nullable=False)
    structured_profile = Column(Text, nullable=False)  # JSON string of the profile

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
        ORDER BY alertAt DESC NULLS LAST
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