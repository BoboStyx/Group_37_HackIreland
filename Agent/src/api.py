"""
FastAPI web API endpoints for the AI agent.
"""
import logging
from typing import Optional, Dict, List, Any
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from datetime import datetime, timedelta
from sqlalchemy import text

from agent import AIAgent
from database import (
    get_db,
    DatabaseError,
    get_tasks_by_urgency,
    update_task_status,
    create_task,
    get_task_by_id,
    update_task_urgency,
    append_task_notes,
    update_task_description,
    create_event,
    get_events_by_timeframe,
    update_event,
    delete_event
)
from server_config import server_config
from o3_mini import O3MiniAgent
from profile_manager import ProfileManager
from linkedin_manager import LinkedInManager
from get_mail import authenticator, get_last_month_emails
from email_processor import EmailProcessor

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
profile_manager = ProfileManager()
linkedin_manager = LinkedInManager()

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

class TaskCreate(BaseModel):
    """Model for creating new tasks."""
    description: str = Field(..., description="Task description")
    urgency: int = Field(..., description="Task urgency (1-5)")
    status: str = Field("pending", description="Initial task status")
    alert_at: Optional[datetime] = Field(None, description="Optional alert time")

class TaskUpdate(BaseModel):
    """Model for task update requests."""
    task_id: int = Field(..., description="Task ID")
    status: str = Field(..., description="New task status")
    alert_at: Optional[datetime] = Field(None, description="Optional alert time")

class TaskUrgencyUpdate(BaseModel):
    """Model for updating task urgency."""
    task_id: int = Field(..., description="Task ID")
    urgency: int = Field(..., description="New urgency level (1-5)")

class TaskNotesUpdate(BaseModel):
    """Model for appending notes to a task."""
    task_id: int = Field(..., description="Task ID")
    notes: str = Field(..., description="Notes to append")

class TaskDescriptionUpdate(BaseModel):
    """Model for updating task description."""
    task_id: int = Field(..., description="Task ID")
    description: str = Field(..., description="New description")

class ProfileInput(BaseModel):
    """Model for profile input."""
    text: str = Field(..., description="Profile information text")
    is_direct_input: bool = Field(True, description="Whether this is direct profile input")

class ProfileResponse(BaseModel):
    """Model for profile responses."""
    profile: Dict[str, Any] = Field(..., description="Structured profile data")
    insight: Optional[str] = Field(None, description="Optional insight gained from profile update")

class RawProfile(BaseModel):
    """Model for raw profile data."""
    raw_input: str = Field(..., description="Raw profile input")
    created_at: str = Field(..., description="Profile creation timestamp")
    updated_at: str = Field(..., description="Profile last update timestamp")

class ThinkDeepRequest(BaseModel):
    """Model for deep thinking requests."""
    prompt: str = Field(..., description="Prompt for deep thinking")

class ThinkDeepResponse(BaseModel):
    """Model for deep thinking responses."""
    result: str = Field(..., description="Deep thinking result")

class LinkedInToken(BaseModel):
    """Model for LinkedIn access token."""
    access_token: str = Field(..., description="OAuth access token from LinkedIn")

# Add new Gmail models
class GmailAuthResponse(BaseModel):
    """Model for Gmail authentication response."""
    auth_url: str = Field(..., description="URL for Gmail OAuth authentication")
    state: str = Field(..., description="State token for verification")

class GmailAuthCallback(BaseModel):
    """Model for Gmail OAuth callback."""
    code: str = Field(..., description="Authorization code from Google")
    state: str = Field(..., description="State token for verification")

class GmailProcessResponse(BaseModel):
    """Model for Gmail processing response."""
    tasks_created: int = Field(..., description="Number of tasks created")
    opportunities_created: int = Field(..., description="Number of opportunities created")
    emails_processed: int = Field(..., description="Number of emails processed")
    status: str = Field(..., description="Processing status")

class GmailAuthStatus(BaseModel):
    """Model for Gmail authentication status."""
    is_authenticated: bool = Field(..., description="Whether Gmail is authenticated")
    email: Optional[str] = Field(None, description="Authenticated Gmail address")
    last_sync: Optional[datetime] = Field(None, description="Last email sync time")

# Add new models for user token
class UserToken(BaseModel):
    """Model for user token."""
    token: str = Field(..., description="User's authentication token")

class ClearChatResponse(BaseModel):
    """Model for clear chat response."""
    message: str = Field(..., description="Status message")
    conversations_deleted: int = Field(..., description="Number of conversations deleted")

class EventBase(BaseModel):
    """Base model for event data."""
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    start_time: datetime = Field(..., description="Event start time")
    end_time: Optional[datetime] = Field(None, description="Event end time")
    location: Optional[str] = Field(None, description="Event location")
    participants: Optional[List[str]] = Field(None, description="List of participants")
    source: Optional[str] = Field(None, description="Source of the event")
    source_link: Optional[str] = Field(None, description="Link to event source")

class EventCreate(EventBase):
    """Model for creating a new event."""
    pass

class EventUpdate(EventBase):
    """Model for updating an event."""
    title: Optional[str] = None
    start_time: Optional[datetime] = None

class EventResponse(EventBase):
    """Model for event responses."""
    id: int = Field(..., description="Event ID")
    created_at: datetime = Field(..., description="Event creation timestamp")
    updated_at: datetime = Field(..., description="Event last update timestamp")

    class Config:
        from_attributes = True

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
        # Collect all chunks from the async generator
        response_chunks = []
        async for chunk in agent.process_input(user_input.text, user_input.context):
            response_chunks.append(chunk)
        
        # Join all chunks into a single response
        response = "".join(response_chunks)
        
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

@app.post("/tasks", status_code=201)
async def create_new_task(task_data: TaskCreate):
    """
    Create a new task.
    """
    try:
        task_id = create_task(
            description=task_data.description,
            urgency=task_data.urgency,
            status=task_data.status,
            alert_at=task_data.alert_at
        )
        return {"task_id": task_id, "message": "Task created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """
    Get a specific task by ID.
    """
    try:
        task = get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/{task_id}/status")
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

@app.post("/tasks/{task_id}/urgency")
async def update_task_urgency_endpoint(task_update: TaskUrgencyUpdate):
    """
    Update a task's urgency level.
    """
    try:
        # Verify task exists
        task = get_task_by_id(task_update.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        update_task_urgency(task_update.task_id, task_update.urgency)
        return {"message": f"Task {task_update.task_id} urgency updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating task urgency: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/{task_id}/notes")
async def append_task_notes_endpoint(notes_update: TaskNotesUpdate):
    """
    Append notes to a task.
    """
    try:
        # Verify task exists
        task = get_task_by_id(notes_update.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        append_task_notes(notes_update.task_id, notes_update.notes)
        return {"message": f"Notes appended to task {notes_update.task_id} successfully"}
    except Exception as e:
        logger.error(f"Error appending task notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tasks/{task_id}/description")
async def update_task_description_endpoint(desc_update: TaskDescriptionUpdate):
    """
    Update a task's description.
    """
    try:
        # Verify task exists
        task = get_task_by_id(desc_update.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        update_task_description(desc_update.task_id, desc_update.description)
        return {"message": f"Task {desc_update.task_id} description updated successfully"}
    except Exception as e:
        logger.error(f"Error updating task description: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/profile", response_model=ProfileResponse)
async def update_profile(profile_input: ProfileInput):
    """
    Update user profile with new information.
    """
    try:
        profile, insight = await profile_manager.process_input(
            profile_input.text,
            profile_input.is_direct_input
        )
        return ProfileResponse(profile=profile, insight=insight)
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile", response_model=Dict[str, Any])
async def get_profile():
    """
    Get the current user profile.
    """
    try:
        profile = await profile_manager.get_profile()
        return profile
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile/raw", response_model=Optional[RawProfile])
async def get_raw_profile():
    """
    Get the raw profile data including history.
    """
    try:
        profile = await profile_manager.get_raw_profile()
        if not profile:
            raise HTTPException(status_code=404, detail="No profile found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting raw profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/profile")
async def clear_profile():
    """
    Clear the user's profile history.
    """
    try:
        success = await profile_manager.clear_profile()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to clear profile")
        return {"message": "Profile cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing profile: {str(e)}")
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

@app.post("/profile/linkedin", response_model=ProfileResponse)
async def update_profile_from_linkedin(token: LinkedInToken):
    """
    Update user profile with LinkedIn data.
    """
    try:
        profile, insight = await linkedin_manager.process_linkedin_profile(token.access_token)
        return ProfileResponse(profile=profile, insight=insight)
    except Exception as e:
        logger.error(f"Error updating profile from LinkedIn: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/gmail/auth", response_model=GmailAuthResponse)
async def start_gmail_auth(user_token: UserToken):
    """
    Start Gmail OAuth authentication process.
    Returns a URL that the user should visit to authorize the application.
    """
    try:
        flow = await authenticator(return_auth_url=True)
        return GmailAuthResponse(
            auth_url=flow.authorization_url()[0],
            state=flow.state
        )
    except Exception as e:
        logger.error(f"Error starting Gmail auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start Gmail authentication")

@app.get("/gmail/status", response_model=GmailAuthStatus)
async def get_gmail_status(user_token: str = Header(...)):
    """
    Check Gmail authentication status.
    Returns whether Gmail is authenticated and the associated email address.
    """
    try:
        status = await check_gmail_auth(user_token)
        return GmailAuthStatus(
            is_authenticated=status['is_authenticated'],
            email=status.get('email'),
            last_sync=status.get('last_sync')
        )
    except Exception as e:
        logger.error(f"Error checking Gmail status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check Gmail status")

@app.post("/gmail/revoke")
async def revoke_gmail_access(user_token: str = Header(...)):
    """
    Revoke Gmail access and clear stored credentials.
    """
    try:
        await revoke_gmail_credentials(user_token)
        return {"message": "Gmail access revoked successfully"}
    except Exception as e:
        logger.error(f"Error revoking Gmail access: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke Gmail access")

@app.post("/gmail/callback", response_model=Dict[str, str])
async def gmail_auth_callback(callback_data: GmailAuthCallback, user_token: str = Header(...)):
    """
    Handle Gmail OAuth callback and store credentials.
    """
    try:
        flow = await authenticator(state=callback_data.state)
        credentials = flow.fetch_token(code=callback_data.code)
        
        # Get user email for confirmation
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email = profile['emailAddress']
        
        # Store credentials securely with user token
        await store_gmail_credentials(user_token, credentials, email)
        
        return {
            "message": f"Gmail authentication successful for {email}",
            "email": email
        }
    except Exception as e:
        logger.error(f"Error in Gmail callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to complete Gmail authentication")

@app.post("/gmail/process", response_model=GmailProcessResponse)
async def process_gmail(background_tasks: BackgroundTasks, user_token: str = Header(...)):
    """
    Process Gmail messages and create tasks/opportunities.
    This is an async operation that runs in the background.
    """
    try:
        # Check authentication first
        status = await check_gmail_auth(user_token)
        if not status['is_authenticated']:
            raise HTTPException(status_code=401, detail="Gmail not authenticated")
        
        # Start processing in the background
        background_tasks.add_task(process_gmail_background, user_token)
        
        return GmailProcessResponse(
            tasks_created=0,
            opportunities_created=0,
            emails_processed=0,
            status="processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting Gmail processing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start Gmail processing")

async def process_gmail_background(user_token: str):
    """Background task for processing Gmail messages."""
    try:
        # Get Gmail service
        service = await authenticator(user_id=user_token)
        
        # Fetch emails
        await get_last_month_emails(service)
        
        # Process emails
        processor = EmailProcessor()
        async with get_db() as db:
            created_items = await processor.process_emails(db)
            
        # Log results
        tasks = [item for item in created_items if item['type'] == 'task']
        opportunities = [item for item in created_items if item['type'] == 'opportunity']
        
        logger.info(f"Gmail processing complete. Created {len(tasks)} tasks and {len(opportunities)} opportunities")
        
    except Exception as e:
        logger.error(f"Error in background Gmail processing: {str(e)}")

@app.post("/chat/clear", response_model=ClearChatResponse)
async def clear_chat(user_token: str = Header(...)):
    """
    Clear the chat history for the user.
    This will remove all conversations from the database and clear the context.
    """
    try:
        # Clear conversations from database
        with get_db() as db:
            # Count conversations before deletion for response
            count_query = text("SELECT COUNT(*) FROM conversations")
            result = db.execute(count_query)
            conversations_count = result.scalar()
            
            # Delete all conversations
            delete_query = text("DELETE FROM conversations")
            db.execute(delete_query)
            db.commit()
            
            # Reset the agent's context if it exists
            if hasattr(agent, 'context'):
                agent.context = {
                    "history": [],
                    "available_tasks": [],
                    "current_task_id": None
                }
                
            return ClearChatResponse(
                message="Chat history cleared successfully",
                conversations_deleted=conversations_count
            )
            
    except Exception as e:
        logger.error(f"Error clearing chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear chat history")

@app.post("/events", response_model=EventResponse)
async def create_new_event(event: EventCreate):
    """
    Create a new event.
    """
    try:
        event_id = create_event(
            title=event.title,
            description=event.description,
            start_time=event.start_time,
            end_time=event.end_time,
            location=event.location,
            participants=event.participants,
            source=event.source,
            source_link=event.source_link
        )
        
        # Get the created event
        with get_db() as db:
            created_event = db.query(Event).filter(Event.id == event_id).first()
            if not created_event:
                raise HTTPException(status_code=404, detail="Created event not found")
            return created_event
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int):
    """
    Get a specific event by ID.
    """
    try:
        with get_db() as db:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            return event
    except Exception as e:
        logger.error(f"Error getting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events", response_model=List[EventResponse])
async def get_events(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
):
    """
    Get events within a timeframe. If no timeframe is specified,
    returns events for the next 30 days.
    """
    try:
        # Default to next 30 days if no timeframe specified
        if not start:
            start = datetime.utcnow()
        if not end:
            end = start + timedelta(days=30)
            
        events = get_events_by_timeframe(start, end)
        return events
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/events/{event_id}", response_model=EventResponse)
async def update_event_endpoint(event_id: int, event_update: EventUpdate):
    """
    Update an event's details.
    """
    try:
        # Convert model to dict, excluding None values
        update_data = event_update.dict(exclude_unset=True)
        update_event(event_id, **update_data)
        
        # Get updated event
        with get_db() as db:
            updated_event = db.query(Event).filter(Event.id == event_id).first()
            if not updated_event:
                raise HTTPException(status_code=404, detail="Event not found")
            return updated_event
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/events/{event_id}")
async def delete_event_endpoint(event_id: int):
    """
    Delete an event.
    """
    try:
        delete_event(event_id)
        return {"message": f"Event {event_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def start_api():
    """Start the FastAPI server."""
    uvicorn.run(
        app,
        host=server_config.api_host,
        port=server_config.api_port,
        workers=server_config.api_workers,
        timeout_keep_alive=server_config.api_timeout
    ) 