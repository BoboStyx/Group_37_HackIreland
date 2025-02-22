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
    query = text("SELECT * FROM tasks WHERE urgency = :urgency")
    with engine.connect() as conn:
        result = conn.execute(query, {"urgency": urgency_level})
        tasks = [dict(row) for row in result]
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