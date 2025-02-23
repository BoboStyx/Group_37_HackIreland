#!./venv/bin/python
"""
Email processing system using Gemini AI for content analysis and task categorization.
"""
import os
from typing import List, Dict, Any, Optional, Tuple
import google.generativeai as genai
from datetime import datetime
import json
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from Pull import db_to_ai
from Agent.src.database import (
    create_task, 
    update_task_urgency,
    append_task_notes,
    UserProfile,
    SessionLocal,
    get_db
)

# Configure Gemini AI with proper settings
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

# Load Gemini AI configuration
GENERATION_CONFIG = {
    'temperature': float(os.getenv('GEMINI_TEMPERATURE', 0.7)),
    'top_k': int(os.getenv('GEMINI_TOP_K', 40)),
    'top_p': float(os.getenv('GEMINI_TOP_P', 0.95)),
    'max_output_tokens': int(os.getenv('GEMINI_MAX_TOKENS', 1024)),
}

class EmailProcessor:
    def __init__(self, use_test_db: bool = False):
        """
        Initialize the email processor.
        
        Args:
            use_test_db: Whether to use test database instead of production
        """
        self.use_test_db = use_test_db
        self.model = genai.GenerativeModel('gemini-pro',
                                         generation_config=GENERATION_CONFIG)
        
    async def process_emails(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Process emails and create tasks/opportunities based on content.
        
        Args:
            db: Database session for user profile access
            
        Returns:
            List of created tasks/opportunities
        """
        # Get user profile from database
        user_profile = await self._get_user_profile(db)
        
        # Get emails from appropriate source
        emails = self._get_emails()
        if not emails:
            return []
            
        created_items = []
        for email in emails:
            # Convert datetime to string for JSON serialization
            if isinstance(email.get('sent_at'), datetime):
                email['sent_at'] = email['sent_at'].isoformat()
                
            items = await self._analyze_email(email, user_profile)
            created_items.extend(items)
            
        return created_items
    
    async def _get_user_profile(self, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get user profile from database."""
        try:
            # Query the most recent user profile
            result = await db.execute(
                "SELECT raw_input, structured_profile FROM user_profiles ORDER BY updated_at DESC LIMIT 1"
            )
            profile = result.first()
            
            if profile:
                # Combine raw input and structured profile
                structured = json.loads(profile.structured_profile)
                return {
                    "interests": structured.get("interests", []),
                    "goals": structured.get("goals", []),
                    "role": structured.get("role", "Not specified"),
                    "preferences": structured.get("preferences", []),
                    "raw_input": profile.raw_input
                }
            return None
            
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            return None
    
    def _get_emails(self) -> List[Dict[str, Any]]:
        """Get emails from either test or production database."""
        if self.use_test_db:
            return self._get_test_emails()
        return db_to_ai()
    
    def _get_test_emails(self) -> List[Dict[str, Any]]:
        """Get emails from test database."""
        # Example test emails matching Pull.py format
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
    
    async def _analyze_email(self, email: Dict[str, Any], user_profile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze an email using Gemini AI and create appropriate tasks/opportunities.
        
        Args:
            email: Email dictionary containing subject, body, etc.
            user_profile: Optional user profile for relevance scoring
            
        Returns:
            List of created tasks/opportunities
        """
        # Prepare prompt for Gemini AI
        prompt = self._create_analysis_prompt(email, user_profile)
        
        try:
            # Get Gemini's analysis with proper async handling
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=GENERATION_CONFIG
            )
            
            # Extract the text content and parse JSON
            if not response.text:
                print("Empty response from Gemini AI")
                return []
                
            try:
                analysis = json.loads(response.text)
            except json.JSONDecodeError:
                # If response isn't valid JSON, try to extract JSON from the text
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    analysis = json.loads(text[start:end])
                else:
                    print("Invalid JSON response from Gemini AI")
                    return []
            
            # Create tasks and opportunities based on analysis
            created_items = []
            
            # Process tasks
            for task in analysis.get('tasks', []):
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
            
            # Process opportunities
            for opp in analysis.get('opportunities', []):
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
            
            return created_items
            
        except Exception as e:
            print(f"Error analyzing email: {str(e)}")
            return []
    
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
                
        prompt = f"""You are an intelligent email analyzer focused on identifying actionable tasks and valuable opportunities. Your goal is to carefully analyze each email while considering the user's profile and context.

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

3. Critical Filtering:
   - Not every email needs a task or opportunity
   - Focus on actionable items and meaningful opportunities
   - Ignore routine notifications unless they require action
   - Pay special attention to:
     * Direct requests or assignments
     * Deadlines or schedule changes
     * Important updates requiring action
     * Opportunities matching user's interests/goals

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
    ]
}}

Only include genuine tasks and opportunities. If none are found, return empty lists.
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
        """Create a task from Gemini's analysis."""
        try:
            # Create base task with source reference
            description = task['description']
            if not description.endswith(']'):  # Add source reference if not already present
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
            print(f"Error creating task: {str(e)}")
            return None
    
    async def _create_opportunity_from_analysis(self, opp: Dict[str, Any], email: Dict[str, Any]) -> Optional[int]:
        """Create an opportunity from Gemini's analysis."""
        try:
            # Create description with source reference
            description = f"[Opportunity] {opp['description']}"
            if not description.endswith(']'):  # Add source reference if not already present
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
            print(f"Error creating opportunity: {str(e)}")
            return None 