"""
FastAPI web API endpoints for the AI agent.
"""
import logging
from typing import Optional, Dict, List, Any
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from datetime import datetime
from sqlalchemy import text

from agent import AIAgent
from database import (
    get_db,
    DatabaseError,
    get_tasks_by_urgency,
    update_task_status,
    create_task,
    get_task_by_id
)
from server_config import server_config
from o3_mini import O3MiniAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO if not server_config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=server_config.api_title,
    version=server_config.api_version,
    description=server_config.api_description,
    debug=server_config.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
agent = AIAgent()
o3_mini = O3MiniAgent()

class UserInput(BaseModel):
    """Model for user input requests."""
    text: str = Field(..., description="User input text")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context")

class AgentResponse(BaseModel):
    """Model for agent responses."""
    response: str = Field(..., description="Agent's response")
    model_used: str = Field(..., description="Model used for processing")

class TaskSummary(BaseModel):
    """Model for task summaries."""
    summaries: List[str] = Field(..., description="List of task summaries")

class TaskUpdate(BaseModel):
    """Model for task update requests."""
    task_id: int = Field(..., description="Task ID")
    status: str = Field(..., description="New task status")
    alert_at: Optional[datetime] = Field(None, description="Optional alert time")

class ThinkDeepRequest(BaseModel):
    """Model for deep thinking requests."""
    prompt: str = Field(..., description="Prompt for deep thinking")

class ThinkDeepResponse(BaseModel):
    """Model for deep thinking responses."""
    result: str = Field(..., description="Deep thinking result")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    """Handle database errors."""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Database operation failed"}
    )

@app.post("/process", response_model=AgentResponse)
async def process_input(user_input: UserInput):
    """
    Process user input and return the agent's response.
    """
    logger.info(f"Processing input: {user_input.text[:100]}...")
    try:
        response = await agent.process_input(user_input.text, user_input.context)
        return AgentResponse(
            response=response,
            model_used=agent.last_model_used
        )
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks", response_model=TaskSummary)
async def get_tasks(urgency: Optional[int] = None):
    """
    Retrieve and summarize tasks ordered by urgency.
    
    Args:
        urgency: Optional urgency level filter (1-5)
    """
    try:
        # Get tasks filtered by urgency if specified
        if urgency is not None:
            tasks = get_tasks_by_urgency(urgency)
        else:
            all_tasks = []
            for level in range(5, 0, -1):
                tasks = get_tasks_by_urgency(level)
                all_tasks.extend(tasks)
            tasks = all_tasks

        # Chunk and summarize tasks
        task_chunks = agent._chunk_tasks(tasks)
        summaries = []
        for chunk in task_chunks:
            chunk_text = agent._format_tasks_for_summary(chunk)
            summary = await agent.chatgpt.summarize_tasks(chunk_text)
            summaries.append(summary)

        return TaskSummary(summaries=summaries)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_task")
async def update_task(task_update: TaskUpdate):
    """
    Update a task's status and alert time.
    """
    try:
        # Verify task exists
        task = get_task_by_id(task_update.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        update_task_status(
            task_update.task_id,
            task_update.status,
            task_update.alert_at
        )
        return {"message": f"Task {task_update.task_id} updated successfully"}
    except DatabaseError as e:
        # Will be handled by the database_error_handler
        raise
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/think_deep", response_model=ThinkDeepResponse)
async def think_deep(request: ThinkDeepRequest):
    """
    Process a deep thinking request using the O3-mini model.
    """
    try:
        if not o3_mini.is_available:
            raise HTTPException(
                status_code=503,
                detail="O3-mini model is not available"
            )
        
        result = await o3_mini.think_deep(request.prompt)
        return ThinkDeepResponse(result=result)
    except Exception as e:
        logger.error(f"Error in deep thinking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        with get_db() as db:
            db.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "environment": server_config.environment,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

def start_api():
    """Start the FastAPI server."""
    uvicorn.run(
        app,
        host=server_config.api_host,
        port=server_config.api_port,
        workers=server_config.api_workers,
        timeout_keep_alive=server_config.api_timeout
    ) 