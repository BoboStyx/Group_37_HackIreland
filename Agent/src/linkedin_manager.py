"""
LinkedIn profile integration manager.
"""
import logging
from typing import Dict, Any, Optional, Tuple
import json
import requests
from datetime import datetime

from profile_manager import ProfileManager

logger = logging.getLogger(__name__)

class LinkedInManager:
    def __init__(self):
        """Initialize the LinkedIn manager."""
        self.profile_manager = ProfileManager()
        
    async def process_linkedin_profile(self, access_token: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Process a LinkedIn profile using the access token.
        
        Args:
            access_token: OAuth access token for LinkedIn API
            
        Returns:
            Tuple[Dict[str, Any], Optional[str]]: Updated profile and insight message
        """
        try:
            # Get basic profile info
            profile_data = self._get_linkedin_profile(access_token)
            
            # Get additional profile sections
            profile_data.update(self._get_linkedin_experience(access_token))
            profile_data.update(self._get_linkedin_education(access_token))
            profile_data.update(self._get_linkedin_skills(access_token))
            
            # Format profile data for processing
            formatted_data = self._format_linkedin_data(profile_data)
            
            # Process through profile manager
            return await self.profile_manager.process_input(
                formatted_data,
                is_direct_input=True
            )
            
        except Exception as e:
            logger.error(f"Error processing LinkedIn profile: {str(e)}")
            raise
            
    def _get_linkedin_profile(self, access_token: str) -> Dict[str, Any]:
        """Get basic LinkedIn profile information."""
        url = "https://api.linkedin.com/v2/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
        
    def _get_linkedin_experience(self, access_token: str) -> Dict[str, Any]:
        """Get LinkedIn experience information."""
        url = "https://api.linkedin.com/v2/positions"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return {"positions": response.json().get("elements", [])}
        
    def _get_linkedin_education(self, access_token: str) -> Dict[str, Any]:
        """Get LinkedIn education information."""
        url = "https://api.linkedin.com/v2/educations"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return {"education": response.json().get("elements", [])}
        
    def _get_linkedin_skills(self, access_token: str) -> Dict[str, Any]:
        """Get LinkedIn skills information."""
        url = "https://api.linkedin.com/v2/skills"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return {"skills": response.json().get("elements", [])}
        
    def _format_linkedin_data(self, profile_data: Dict[str, Any]) -> str:
        """Format LinkedIn profile data into a structured string."""
        formatted = []
        
        # Basic info
        if "localizedFirstName" in profile_data and "localizedLastName" in profile_data:
            formatted.append(f"Name: {profile_data['localizedFirstName']} {profile_data['localizedLastName']}")
            
        if "headline" in profile_data:
            formatted.append(f"Headline: {profile_data['headline']}")
            
        # Experience
        if "positions" in profile_data and profile_data["positions"]:
            formatted.append("\nWork Experience:")
            for position in profile_data["positions"]:
                company = position.get("companyName", "Unknown Company")
                title = position.get("title", "Unknown Title")
                start_date = position.get("startDate", {})
                start = f"{start_date.get('month', '')}/{start_date.get('year', '')}"
                end_date = position.get("endDate", {})
                end = f"{end_date.get('month', '')}/{end_date.get('year', '')}" if end_date else "Present"
                description = position.get("description", "")
                formatted.append(f"- {title} at {company} ({start} - {end})")
                if description:
                    formatted.append(f"  {description}")
                    
        # Education
        if "education" in profile_data and profile_data["education"]:
            formatted.append("\nEducation:")
            for edu in profile_data["education"]:
                school = edu.get("schoolName", "Unknown School")
                degree = edu.get("degreeName", "")
                field = edu.get("fieldOfStudy", "")
                start_date = edu.get("startDate", {})
                start = f"{start_date.get('year', '')}"
                end_date = edu.get("endDate", {})
                end = f"{end_date.get('year', '')}" if end_date else "Present"
                formatted.append(f"- {degree} {field} at {school} ({start} - {end})")
                
        # Skills
        if "skills" in profile_data and profile_data["skills"]:
            formatted.append("\nSkills:")
            skills = [skill.get("name", "") for skill in profile_data["skills"]]
            formatted.append("- " + ", ".join(skills))
            
        return "\n".join(formatted) 