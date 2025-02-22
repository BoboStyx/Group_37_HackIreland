"""
Profile management and generation for the AI agent.
"""
from typing import Optional, Dict, Any, Tuple
import logging
from datetime import datetime
import json
import re

from chatgpt_agent import ChatGPTAgent
from database import SessionLocal, Base, UserProfile
from sqlalchemy import Column, Integer, String, Text, DateTime

logger = logging.getLogger(__name__)

class ProfileManager:
    def __init__(self, debug_profile: bool = False):
        """Initialize the profile manager."""
        self.chatgpt = ChatGPTAgent()
        self.debug_profile = debug_profile

    def _log_profile_debug(self, message: str, data: Any = None):
        """Helper method to log profile-related debug information."""
        if self.debug_profile:
            if data:
                logger.info(f"{message}: {json.dumps(data, indent=2)}")
            else:
                logger.info(message)

    async def clear_profile(self) -> bool:
        """
        Clear the user's profile history.
        
        Returns:
            bool: True if successful, False otherwise
        """
        db = SessionLocal()
        try:
            self._log_profile_debug("Attempting to clear profile history")
            db.query(UserProfile).delete()
            db.commit()
            self._log_profile_debug("Successfully cleared profile history")
            return True
        except Exception as e:
            logger.error(f"Error clearing profile: {str(e)}")
            db.rollback()
            return False
        finally:
            db.close()

    async def process_input(self, input_text: str, is_direct_input: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Process any input text to extract and update user profile information.
        
        Args:
            input_text: The text to process (could be direct profile input or conversation)
            is_direct_input: Whether this is direct profile input vs conversation
            
        Returns:
            Tuple[Dict[str, Any], Optional[str]]: Updated profile and insight message if profile was updated
        """
        db = SessionLocal()  # Create a new session for this operation
        try:
            # First, analyze the input for relevant user information
            analysis_prompt = f"""Analyze this {'profile information' if is_direct_input else 'conversation'} for relevant details about the user.
            
            Input:
            {input_text}
            
            If this is direct profile input, extract all relevant information.
            If this is conversation, only extract information if it reveals something meaningful about the user's:
            - Name: The user's name if provided (e.g., "My name is Bob")
            - Background
            - Experience
            - Interests
            - Goals
            - Skills
            - Preferences
            - Work style
            - Domain knowledge
            
            Format your response EXACTLY as follows (including the triple backticks):
            ```json
            {{
                "has_relevant_info": boolean indicating if meaningful user information was found,
                "extracted_info": {{ information organized by category }},
                "confidence": rating from 0-1 for how confident we are in the extracted information,
                "reasoning": "brief explanation of why this information is relevant to the user profile"
            }}
            ```
            
            Only extract information that is clearly about the user (not about others or general topics).
            If no relevant information is found, set has_relevant_info to false and leave other fields empty.
            IMPORTANT: Ensure the response is valid JSON within the triple backticks."""

            # Get the analysis from ChatGPT
            analysis = ""
            async for chunk in self.chatgpt.process(analysis_prompt, {"task": "profile_analysis"}):
                analysis += chunk

            # Extract JSON from between triple backticks
            try:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis, re.DOTALL)
                if not json_match:
                    logger.warning("No JSON found in response")
                    return {}, None
                
                # Parse the analysis
                analysis_data = json.loads(json_match.group(1))
            except (json.JSONDecodeError, AttributeError) as e:
                logger.error(f"Failed to parse analysis response: {e}")
                logger.debug(f"Raw response: {analysis}")
                return {}, None
            
            if not analysis_data.get('has_relevant_info', False):
                return {}, None

            # If we have relevant info, get the current profile or create a new one
            profile_record = db.query(UserProfile).first()
            if not profile_record:
                profile_record = UserProfile(
                    created_at=datetime.utcnow(),
                    raw_input="",
                    structured_profile=json.dumps({"_meta": {"created_at": datetime.utcnow().isoformat()}})
                )
                db.add(profile_record)
                db.flush()  # Flush to get the ID

            current_profile = json.loads(profile_record.structured_profile)
            
            # Log the analysis data
            self._log_profile_debug("Analysis data", analysis_data)
            
            # Merge the new information
            merge_prompt = f"""Merge this new user information into their existing profile. If the new information includes a name, update or add it under the key "name".
            
            Current profile:
            {json.dumps(current_profile, indent=2)}
            
            New information:
            {json.dumps(analysis_data['extracted_info'], indent=2)}
            
            Confidence in new information: {analysis_data['confidence']}
            
            Format your response EXACTLY as follows (including the triple backticks):
            ```json
            {{
                "profile": {{ complete merged profile as a JSON object }},
                "insight": "brief note about what was learned about the user"
            }}
            ```
            
            Rules:
            1. Preserve existing information unless new information is more specific or has higher confidence
            2. Add new information in appropriate sections
            3. Resolve any conflicts in favor of more recent, more specific, or higher confidence information
            4. Maintain a natural, coherent profile structure
            5. Keep the profile concise but detailed
            
            IMPORTANT: Ensure the response is valid JSON within the triple backticks."""

            # Get the merged profile from ChatGPT
            merge_result = ""
            async for chunk in self.chatgpt.process(merge_prompt, {"task": "profile_merge"}):
                merge_result += chunk

            # Extract and parse the merge result
            try:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', merge_result, re.DOTALL)
                if not json_match:
                    logger.warning("No JSON found in merge response")
                    return current_profile, None
                
                merge_data = json.loads(json_match.group(1))
                updated_profile = merge_data['profile']
                insight = merge_data['insight']
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.error(f"Failed to parse merge response: {e}")
                self._log_profile_debug("Raw response", merge_result)
                return current_profile, None
            
            # Log the current profile before merge
            self._log_profile_debug("Current profile before merge", current_profile)
            
            # Update metadata
            if '_meta' not in updated_profile:
                updated_profile['_meta'] = {}
            updated_profile['_meta'].update({
                'last_updated': datetime.utcnow().isoformat(),
                'last_update_type': 'direct_input' if is_direct_input else 'conversation_insight',
                'last_update_confidence': analysis_data['confidence']
            })
            
            # Log the merge result
            self._log_profile_debug("Merge result", merge_data)
            
            # Update the database record
            profile_record.raw_input = (
                f"{profile_record.raw_input}\n\n"
                f"--- {'Direct Input' if is_direct_input else 'Conversation Insight'} "
                f"({datetime.utcnow().isoformat()}) ---\n{input_text}"
            )
            profile_record.structured_profile = json.dumps(updated_profile)
            profile_record.updated_at = datetime.utcnow()
            
            # Log the final profile being saved
            self._log_profile_debug("Saving updated profile", updated_profile)
            
            # Commit the transaction
            self._log_profile_debug("Committing profile update to database...")
            db.commit()
            self._log_profile_debug(f"Successfully committed profile update. Profile ID: {profile_record.id}")
            
            return updated_profile, insight

        except Exception as e:
            logger.error(f"Error processing profile input: {str(e)}")
            self._log_profile_debug("Rolling back database transaction due to error")
            db.rollback()  # Rollback on error
            return {}, None
        finally:
            self._log_profile_debug("Closing database session")
            db.close()  # Always close the session

    async def get_profile(self) -> Dict[str, Any]:
        """
        Retrieve the current profile.
            
        Returns:
            Dict containing the structured profile
        """
        db = SessionLocal()
        try:
            self._log_profile_debug("Querying database for current profile...")
            profile_record = db.query(UserProfile).first()
            if not profile_record:
                self._log_profile_debug("No profile found in database, returning empty profile")
                return {"_meta": {"created_at": datetime.utcnow().isoformat()}}
            
            # Log the actual profile data being retrieved
            profile_data = json.loads(profile_record.structured_profile)
            self._log_profile_debug("Retrieved profile data", profile_data)
            
            self._log_profile_debug(f"Successfully retrieved profile. Profile ID: {profile_record.id}")
            return profile_data
        except Exception as e:
            logger.error(f"Error retrieving profile: {str(e)}")
            return {"_meta": {"created_at": datetime.utcnow().isoformat()}}
        finally:
            self._log_profile_debug("Closing database session")
            db.close()

    async def get_raw_profile(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the raw profile data.
            
        Returns:
            Dict containing raw_input and timestamps, or None if not found
        """
        db = SessionLocal()
        try:
            logger.info("Querying database for raw profile data...")
            profile_record = db.query(UserProfile).first()
            if not profile_record:
                logger.info("No profile found in database")
                return None
            logger.info(f"Successfully retrieved raw profile. Profile ID: {profile_record.id}")
            return {
                'raw_input': profile_record.raw_input,
                'created_at': profile_record.created_at.isoformat(),
                'updated_at': profile_record.updated_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error retrieving raw profile: {str(e)}")
            return None
        finally:
            logger.debug("Closing database session")
            db.close()

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'db') and self.db is not None:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}") 