"""
Database models and interactions for the AI agent system.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text

from config import DATABASE_URL

# Create database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tasks_by_urgency(urgency_level: int) -> List[dict]:
    """
    Retrieve tasks from the database with the specified urgency.
    
    Parameters:
        urgency_level (int): The urgency level to filter tasks (e.g., 5, 4, 3, etc.)
    
    Returns:
        List[dict]: A list of tasks as dictionaries with keys:
                   id, description, urgency, status, and alertAt
    """
    query = text("""
        SELECT id, description, urgency, status, alertAt 
        FROM tasks 
        WHERE urgency = :urgency
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"urgency": urgency_level})
        tasks = []
        for row in result:
            # Convert row to dictionary using column names
            task_dict = {
                'id': row[0],
                'description': row[1],
                'urgency': row[2],
                'status': row[3],
                'alertAt': row[4]
            }
            tasks.append(task_dict)
    return tasks

def update_task_status(task_id: int, status: str, alert_at: Optional[datetime]) -> None:
    """
    Update the status and alert time of a task in the database.
    
    Parameters:
        task_id (int): The unique identifier of the task
        status (str): The new status of the task (e.g., 'pending', 'half-completed', 'completed')
        alert_at (Optional[datetime]): The datetime to set for the alert reminder; can be None
                                     if no reminder is needed
    """
    query = text("""
        UPDATE tasks
        SET status = :status, alertAt = :alert_at
        WHERE id = :task_id
    """)
    with engine.connect() as conn:
        conn.execute(query, {
            "status": status,
            "alert_at": alert_at,
            "task_id": task_id
        })
        conn.commit()

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

def get_task_by_id(task_id: int) -> Optional[dict]:
    """
    Retrieve a single task by its ID.
    
    Parameters:
        task_id (int): The unique identifier of the task
    
    Returns:
        Optional[dict]: The task as a dictionary if found, None otherwise
    """
    query = text("""
        SELECT id, description, urgency, status, alertAt 
        FROM tasks 
        WHERE id = :task_id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"task_id": task_id})
        row = result.fetchone()
        if row is None:
            return None
        return {
            'id': row[0],
            'description': row[1],
            'urgency': row[2],
            'status': row[3],
            'alertAt': row[4]
        } 