"""
FastAPI web API endpoints for the AI agent.
"""
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uvicorn
from datetime import datetime

from agent import AIAgent, chunk_tasks
from database import get_db, SessionLocal, get_tasks_by_urgency, update_task_status
from config import (
    API_HOST, API_PORT, API_TITLE, API_VERSION, API_DESCRIPTION,
    HIGH_PRIORITY_URGENCY_LEVELS
)
from o3_mini import O3MiniAgent

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION
)
agent = AIAgent()
o3_mini = O3MiniAgent()

class UserInput(BaseModel):
    """Model for user input requests."""
    text: str
    context: Optional[Dict] = None

class AgentResponse(BaseModel):
    """Model for agent responses."""
    response: str
    model_used: str

class TaskSummary(BaseModel):
    """Model for task summaries."""
    summaries: List[str]

class TaskUpdate(BaseModel):
    """Model for task update requests."""
    task_id: int
    status: str
    alert_at: Optional[datetime] = None

class ThinkDeepRequest(BaseModel):
    """Model for deep thinking requests."""
    prompt: str

class ThinkDeepResponse(BaseModel):
    """Model for deep thinking responses."""
    result: str

@app.post("/process", response_model=AgentResponse)
async def process_input(user_input: UserInput):
    """
    Process user input and return the agent's response.
    """
    try:
        response = await agent.process_input(user_input.text, user_input.context)
        return AgentResponse(
            response=response,
            model_used="gpt-4"  # This will be updated based on actual model used
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks", response_model=TaskSummary)
async def get_tasks():
    """
    Retrieve and summarize tasks ordered by urgency.
    Returns a summary of tasks chunked and processed for efficient viewing.
    """
    try:
        # Get tasks by high priority urgency levels
        all_tasks = []
        for urgency in HIGH_PRIORITY_URGENCY_LEVELS:
            tasks = get_tasks_by_urgency(urgency)
            all_tasks.extend(tasks)

        # Chunk the tasks
        task_chunks = agent._chunk_tasks(all_tasks)
        
        # Get summaries using ChatGPT
        summaries = []
        for chunk in task_chunks:
            chunk_text = agent._format_tasks_for_summary(chunk)
            summary = await agent.chatgpt.summarize_tasks(chunk_text)
            summaries.append(summary)

        return TaskSummary(summaries=summaries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_task")
async def update_task(task_update: TaskUpdate):
    """
    Update a task's status and alert time.
    """
    try:
        update_task_status(
            task_update.task_id,
            task_update.status,
            task_update.alert_at
        )
        return {"message": f"Task {task_update.task_id} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/think_deep", response_model=ThinkDeepResponse)
async def think_deep(request: ThinkDeepRequest):
    """
    Process a deep thinking request using the O3-mini model.
    This endpoint is designed for complex problems requiring deeper analysis.
    """
    try:
        if not o3_mini.is_available:
            raise HTTPException(
                status_code=503,
                detail="O3-mini model is not available. Please check API configuration."
            )
        
        result = await o3_mini.think_deep(request.prompt)
        return ThinkDeepResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

def start_api():
    """Start the FastAPI server."""
    uvicorn.run(app, host=API_HOST, port=API_PORT) 