from database import Base, engine, SessionLocal, Task
from datetime import datetime

def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Add a sample task
    try:
        session = SessionLocal()
        # Check if we already have tasks
        existing_tasks = session.query(Task).first()
        if not existing_tasks:
            print("Adding sample task...")
            sample_task = Task(
                description="Review project requirements",
                urgency=3,
                status="pending",
                alertAt=datetime.now()
            )
            session.add(sample_task)
            session.commit()
            print("Sample task added successfully!")
        session.close()
    except Exception as e:
        print(f"Error adding sample task: {str(e)}")
    
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_database() 