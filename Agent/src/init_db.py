from database import Base, engine, SessionLocal, Task
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    print("Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Add sample tasks
    try:
        session = SessionLocal()
        print("Adding sample tasks...")
        tasks = [
            Task(
                description="Schedule stakeholder meeting",
                urgency=5,
                status="pending",
                alertAt=datetime.now()
            ),
            Task(
                description="Prepare presentation for team meeting",
                urgency=4,
                status="pending",
                alertAt=datetime.now() + timedelta(days=1)
            ),
            Task(
                description="Review project requirements",
                urgency=3,
                status="pending",
                alertAt=datetime.now()
            ),
            Task(
                description="Update documentation",
                urgency=2,
                status="in_progress",
                alertAt=datetime.now() + timedelta(days=2)
            )
        ]
        
        for task in tasks:
            session.add(task)
            logger.info(f"Added task: {task.description}")
        
        session.commit()
        print("Sample tasks added successfully!")
            
        # Count total tasks
        task_count = session.query(Task).count()
        logger.info(f"Total tasks in database: {task_count}")
        
        session.close()
    except Exception as e:
        print(f"Error adding sample tasks: {str(e)}")
        logger.error(f"Database error: {str(e)}")
    
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_database() 