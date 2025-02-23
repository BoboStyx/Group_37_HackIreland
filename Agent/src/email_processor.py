"""
Email processing system using Gemini AI for content analysis and task categorization.
"""
import os
from typing import List, Dict, Any, Optional, Tuple
import google.generativeai as genai
from datetime import datetime
import json
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from database import (
    create_task,
    update_task_urgency,
    append_task_notes,
    UserProfile,
    get_db,
    DatabaseError,
    create_event
)
from server_config import server_config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not server_config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Gemini AI
if not server_config.gemini_api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=server_config.gemini_api_key)

# Load Gemini AI configuration
GENERATION_CONFIG = {
    'temperature': float(os.getenv('GEMINI_TEMPERATURE', 0.7)),
    'top_k': int(os.getenv('GEMINI_TOP_K', 40)),
    'top_p': float(os.getenv('GEMINI_TOP_P', 0.95)),
    'max_output_tokens': int(os.getenv('GEMINI_MAX_TOKENS', 1024)),
}

class EmailProcessingError(Exception):
    """Custom exception for email processing errors."""
    pass

class EmailProcessor:
    def __init__(self, use_test_db: bool = False):
        """
        Initialize the email processor.
        
        Args:
            use_test_db: Whether to use test database instead of production
        """
        self.use_test_db = use_test_db
        try:
            self.model = genai.GenerativeModel('gemini-pro',
                                             generation_config=GENERATION_CONFIG)
            logger.info("Initialized Gemini AI model")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI model: {str(e)}")
            raise EmailProcessingError("Failed to initialize AI model")
        
    async def process_emails(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Process emails and create tasks/opportunities based on content.
        
        Args:
            db: Database session for user profile access
            
        Returns:
            List of created tasks/opportunities
            
        Raises:
            EmailProcessingError: If processing fails
        """
        try:
            # Get user profile from database
            user_profile = await self._get_user_profile(db)
            
            # Get emails from appropriate source
            emails = await self._get_emails()
            if not emails:
                logger.info("No emails to process")
                return []
                
            created_items = []
            for email in emails:
                try:
                    # Convert datetime to string for JSON serialization
                    if isinstance(email.get('sent_at'), datetime):
                        email['sent_at'] = email['sent_at'].isoformat()
                        
                    items = await self._analyze_email(email, user_profile)
                    created_items.extend(items)
                except Exception as e:
                    logger.error(f"Error processing email {email.get('id')}: {str(e)}")
                    # Continue processing other emails
                    continue
            
            return created_items
            
        except Exception as e:
            logger.error(f"Error in email processing: {str(e)}")
            raise EmailProcessingError(f"Email processing failed: {str(e)}")
    
    async def _get_user_profile(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get user profile from database with error handling."""
        try:
            result = await db.execute(
                "SELECT raw_input, structured_profile FROM user_profiles ORDER BY updated_at DESC LIMIT 1"
            )
            profile = result.first()
            
            if profile:
                try:
                    structured = json.loads(profile.structured_profile)
                    return {
                        "interests": structured.get("interests", []),
                        "goals": structured.get("goals", []),
                        "role": structured.get("role", "Not specified"),
                        "preferences": structured.get("preferences", []),
                        "raw_input": profile.raw_input
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing profile JSON: {str(e)}")
                    return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None
    
    async def _get_emails(self) -> List[Dict[str, Any]]:
        """Get emails with proper error handling."""
        try:
            if self.use_test_db:
                return await self._get_test_emails()
            return await self._get_production_emails()
        except Exception as e:
            logger.error(f"Error getting emails: {str(e)}")
            raise EmailProcessingError(f"Failed to get emails: {str(e)}")
    
    async def _get_test_emails(self) -> List[Dict[str, Any]]:
        """Get emails from test database."""
        current_time = datetime.now()
        return [
            {
                "id": 1,
                "sender": "manager@company.com",
                "recipient": "employee@company.com",
                "subject": "Urgent: Project Deadline Update",
                "body": "The client meeting has been moved to next week. Please prepare the presentation by Tuesday.",
                "sent_at": current_time,
                "user_id": 1,
                "email_link": "https://mail.google.com/mail/u/0/#search/rfc822msgid:test123"
            }
        ]
    
    async def _get_production_emails(self) -> List[Dict[str, Any]]:
        """Get emails from production database with limits."""
        try:
            from Pull import db_to_ai
            return db_to_ai()
        except Exception as e:
            logger.error(f"Error getting production emails: {str(e)}")
            raise EmailProcessingError("Failed to get production emails")
    
    async def _analyze_email(self, email: Dict[str, Any], user_profile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze an email using Gemini AI and create tasks/opportunities/events.
        
        Args:
            email: Email data
            user_profile: Optional user profile for relevance scoring
            
        Returns:
            List of created items
            
        Raises:
            EmailProcessingError: If analysis fails
        """
        try:
            # Prepare prompt for Gemini AI
            prompt = self._create_analysis_prompt(email, user_profile)
            
            # Get Gemini's analysis
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=GENERATION_CONFIG
            )
            
            if not response.text:
                logger.warning("Empty response from Gemini AI")
                return []
                
            try:
                analysis = json.loads(response.text)
            except json.JSONDecodeError:
                # Try to extract JSON from text
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    analysis = json.loads(text[start:end])
                else:
                    logger.error("Invalid JSON response from Gemini AI")
                    return []
            
            # Create tasks, opportunities, and events
            created_items = []
            
            # Process tasks
            for task in analysis.get('tasks', []):
                try:
                    task_id = await self._create_task_from_analysis(task, email)
                    if task_id:
                        created_items.append({
                            'type': 'task',
                            'id': task_id,
                            'source_email': email.get('subject'),
                            'urgency': task.get('urgency', 3),
                            'email_id': email.get('id'),
                            'user_id': email.get('user_id'),
                            'email_link': email.get('email_link')
                        })
                except Exception as e:
                    logger.error(f"Error creating task: {str(e)}")
                    continue
            
            # Process opportunities
            for opp in analysis.get('opportunities', []):
                try:
                    opp_id = await self._create_opportunity_from_analysis(opp, email)
                    if opp_id:
                        created_items.append({
                            'type': 'opportunity',
                            'id': opp_id,
                            'source_email': email.get('subject'),
                            'relevance': opp.get('relevance', 0),
                            'email_id': email.get('id'),
                            'user_id': email.get('user_id'),
                            'email_link': email.get('email_link')
                        })
                except Exception as e:
                    logger.error(f"Error creating opportunity: {str(e)}")
                    continue

            # Process events
            for event in analysis.get('events', []):
                try:
                    event_id = await self._create_event_from_analysis(event, email)
                    if event_id:
                        created_items.append({
                            'type': 'event',
                            'id': event_id,
                            'source_email': email.get('subject'),
                            'email_id': email.get('id'),
                            'user_id': email.get('user_id'),
                            'email_link': email.get('email_link')
                        })
                except Exception as e:
                    logger.error(f"Error creating event: {str(e)}")
                    continue
            
            return created_items
            
        except Exception as e:
            logger.error(f"Error analyzing email: {str(e)}")
            raise EmailProcessingError(f"Failed to analyze email: {str(e)}")
    
    def _create_analysis_prompt(self, email: Dict[str, Any], user_profile: Optional[Dict[str, Any]]) -> str:
        """Create prompt for Gemini AI analysis."""
        # Parse sent_at datetime if it's a string
        sent_at = email.get('sent_at')
        if isinstance(sent_at, str):
            try:
                sent_at = datetime.fromisoformat(sent_at)
            except ValueError:
                sent_at = None
                
        # Determine email client from link
        email_client = "Gmail" if "mail.google.com" in email.get('email_link', '') else "Outlook" if "outlook.office.com" in email.get('email_link', '') else "Email"
                
        prompt = f"""You are an intelligent email analyzer focused on identifying actionable tasks, valuable opportunities, and calendar events. Your goal is to carefully analyze each email while considering the user's profile and context.

Email Details:
- Subject: {email.get('subject')}
- From: {email.get('sender')}
- To: {email.get('recipient')}
- Sent: {sent_at.strftime('%Y-%m-%d %H:%M:%S') if sent_at else 'Unknown'}
- Content: {email.get('body')}

{self._get_profile_context(user_profile)}

Analysis Guidelines:
1. Task Identification:
   - Look for explicit or implied action items
   - Consider deadlines and time-sensitive requests
   - Pay special attention to emails from supervisors or important stakeholders
   - Urgency levels:
     * 5: Immediate attention required (same/next day)
     * 4: Important and time-sensitive (this week)
     * 3: Normal priority tasks
     * 2: Low priority or flexible timeline
     * 1: Optional/FYI tasks

2. Opportunity Detection:
   - Identify learning opportunities, networking chances, or career growth
   - Look for potential collaborations or projects
   - Consider alignment with user's interests and goals
   - Rate relevance based on user's profile (0-100)

3. Event Detection:
   - Look for meeting invites, scheduled calls, or any time-based commitments
   - Extract key event details:
     * Title/Subject
     * Start time and duration/end time
     * Location (physical or virtual)
     * Participants/Attendees
   - Pay attention to:
     * Date and time mentions
     * Meeting links (Zoom, Teams, etc.)
     * Location details
     * RSVP requests

4. Critical Filtering:
   - Not every email needs a task, opportunity, or event
   - Focus on actionable items and meaningful opportunities
   - Ignore routine notifications unless they require action
   - Pay special attention to:
     * Direct requests or assignments
     * Deadlines or schedule changes
     * Important updates requiring action
     * Opportunities matching user's interests/goals
     * Calendar invites or meeting requests

Format your response as JSON with this structure:
{{
    "tasks": [
        {{
            "description": "Task description [Source: sender@email.com - View original email]",
            "urgency": 1-5,
            "deadline": "YYYY-MM-DD" or null,
            "context": "Additional context",
            "participants": ["sender", "recipient", "others mentioned"],
            "source_reference": "View in {email_client}"
        }}
    ],
    "opportunities": [
        {{
            "description": "Opportunity description [Source: sender@email.com - View original email]",
            "relevance": 0-100,
            "category": "Category name",
            "potential_impact": "Description of potential impact",
            "key_stakeholders": ["relevant people"],
            "source_reference": "View in {email_client}"
        }}
    ],
    "events": [
        {{
            "title": "Event title",
            "description": "Event description",
            "start_time": "YYYY-MM-DD HH:MM:SS",
            "end_time": "YYYY-MM-DD HH:MM:SS" or null,
            "location": "Physical location or meeting link",
            "participants": ["list", "of", "participants"],
            "source_reference": "View in {email_client}"
        }}
    ]
}}

Only include genuine tasks, opportunities, and events. If none are found, return empty lists.
Ensure the response is valid JSON."""

        return prompt
    
    def _get_profile_context(self, profile: Optional[Dict[str, Any]]) -> str:
        """Get user profile context for the prompt."""
        if not profile:
            return "No user profile available."
            
        context = f"""User Profile Context:
- Interests: {', '.join(profile.get('interests', []))}
- Goals: {', '.join(profile.get('goals', []))}
- Role: {profile.get('role', 'Not specified')}
- Preferences: {', '.join(profile.get('preferences', []))}"""

        if profile.get('raw_input'):
            context += f"\n\nAdditional Profile Information:\n{profile['raw_input']}"
            
        return context
    
    async def _create_task_from_analysis(self, task: Dict[str, Any], email: Dict[str, Any]) -> Optional[int]:
        """Create a task from Gemini's analysis with error handling."""
        try:
            # Create base task with source reference
            description = task['description']
            if not description.endswith(']'):
                description += f"\n[Source: {email.get('sender')} - View original email]"
            
            task_id = await create_task(
                description=description,
                urgency=task.get('urgency', 3)
            )
            
            # Add context as notes with email link
            context = f"Created from email: {email.get('subject')}\n"
            context += f"From: {email.get('sender')}\n"
            context += f"To: {email.get('recipient')}\n"
            context += f"Sent: {email.get('sent_at')}\n"
            context += f"Original Email: {email.get('email_link')}\n"
            
            if task.get('participants'):
                context += f"\nParticipants: {', '.join(task['participants'])}"
                
            if task.get('context'):
                context += f"\nAdditional Context:\n{task['context']}"
            
            await append_task_notes(task_id, context)
            
            # Update urgency if deadline is soon
            if task.get('deadline'):
                try:
                    deadline = datetime.strptime(task['deadline'], '%Y-%m-%d')
                    days_until = (deadline - datetime.now()).days
                    if days_until <= 2 and task['urgency'] < 5:
                        await update_task_urgency(task_id, 5)
                except ValueError:
                    pass  # Invalid date format
                    
            return task_id
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            return None
    
    async def _create_opportunity_from_analysis(self, opp: Dict[str, Any], email: Dict[str, Any]) -> Optional[int]:
        """Create an opportunity from Gemini's analysis with error handling."""
        try:
            # Create description with source reference
            description = f"[Opportunity] {opp['description']}"
            if not description.endswith(']'):
                description += f"\n[Source: {email.get('sender')} - View original email]"
            
            description += f"\n\nCategory: {opp.get('category', 'Uncategorized')}\n"
            description += f"Potential Impact: {opp.get('potential_impact', 'Not specified')}"
            
            if opp.get('key_stakeholders'):
                description += f"\nKey Stakeholders: {', '.join(opp['key_stakeholders'])}"
            
            task_id = await create_task(
                description=description,
                urgency=1  # Low urgency for opportunities
            )
            
            # Add source context with email link
            context = f"Discovered in email: {email.get('subject')}\n"
            context += f"From: {email.get('sender')}\n"
            context += f"To: {email.get('recipient')}\n"
            context += f"Sent: {email.get('sent_at')}\n"
            context += f"Original Email: {email.get('email_link')}\n"
            context += f"Relevance Score: {opp.get('relevance', 0)}/100"
            
            await append_task_notes(task_id, context)
            return task_id
            
        except Exception as e:
            logger.error(f"Error creating opportunity: {str(e)}")
            return None
    
    async def _create_event_from_analysis(self, event: Dict[str, Any], email: Dict[str, Any]) -> Optional[int]:
        """Create an event from Gemini's analysis."""
        try:
            # Parse datetime strings
            try:
                start_time = datetime.strptime(event['start_time'], '%Y-%m-%d %H:%M:%S')
                end_time = datetime.strptime(event['end_time'], '%Y-%m-%d %H:%M:%S') if event.get('end_time') else None
            except ValueError as e:
                logger.error(f"Error parsing event datetime: {str(e)}")
                return None

            # Create the event
            event_id = create_event(
                title=event['title'],
                description=event.get('description'),
                start_time=start_time,
                end_time=end_time,
                location=event.get('location'),
                participants=event.get('participants'),
                source='email',
                source_link=email.get('email_link')
            )
            
            return event_id
            
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            return None 