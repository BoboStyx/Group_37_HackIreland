"""
Gmail integration for fetching and processing emails.
"""
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import base64
import json
import os
from pathlib import Path
from bs4 import BeautifulSoup
import mysql.connector
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from database import GmailCredentials, get_db

from server_config import server_config, db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not server_config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Secure storage configuration
CREDENTIALS_DIR = Path('.credentials')
CREDENTIALS_FILE = CREDENTIALS_DIR / 'gmail_credentials.enc'
KEY_FILE = CREDENTIALS_DIR / '.key'

class GmailError(Exception):
    """Custom exception for Gmail-related errors."""
    pass

class DatabaseConnectionError(Exception):
    """Custom exception for database connection errors."""
    pass

def get_db_connection():
    """
    Create a database connection with proper error handling.
    
    Returns:
        mysql.connector.connection.MySQLConnection
        
    Raises:
        DatabaseConnectionError: If connection fails
    """
    try:
        config = db_config.get_config(server_config.environment)
        return mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password'],
            database=config['database'],
            port=config['port']
        )
    except mysql.connector.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        raise DatabaseConnectionError(f"Failed to connect to database: {str(e)}")

def get_encryption_key() -> bytes:
    """Get or create encryption key for credentials."""
    if not CREDENTIALS_DIR.exists():
        CREDENTIALS_DIR.mkdir(mode=0o700)
    
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        KEY_FILE.chmod(0o600)
        return key

async def store_gmail_credentials(user_id: str, credentials: Dict[str, Any], email: str) -> None:
    """
    Securely store Gmail credentials in the database.
    
    Args:
        user_id: User's unique identifier
        credentials: OAuth credentials dictionary
        email: Gmail address
    """
    try:
        # Encrypt credentials
        key = get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(json.dumps(credentials).encode())
        
        async with get_db() as db:
            # Check if credentials already exist
            gmail_creds = db.query(GmailCredentials).filter_by(user_id=user_id).first()
            
            if gmail_creds:
                # Update existing credentials
                gmail_creds.credentials = encrypted_data.decode()
                gmail_creds.email = email
                gmail_creds.updated_at = datetime.utcnow()
            else:
                # Create new credentials
                gmail_creds = GmailCredentials(
                    user_id=user_id,
                    credentials=encrypted_data.decode(),
                    email=email
                )
                db.add(gmail_creds)
            
            await db.commit()
        
        logger.info(f"Gmail credentials stored for user {user_id}")
    except Exception as e:
        logger.error(f"Error storing credentials: {str(e)}")
        raise GmailError("Failed to store credentials")

async def load_gmail_credentials(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Load stored Gmail credentials from database.
    
    Args:
        user_id: User's unique identifier
    
    Returns:
        Optional[Dict[str, Any]]: Credentials if found and valid
    """
    try:
        async with get_db() as db:
            gmail_creds = db.query(GmailCredentials).filter_by(user_id=user_id).first()
            
            if not gmail_creds:
                return None
                
            # Decrypt credentials
            key = get_encryption_key()
            f = Fernet(key)
            credentials = json.loads(f.decrypt(gmail_creds.credentials.encode()))
            
            return credentials
    except Exception as e:
        logger.error(f"Error loading credentials: {str(e)}")
        return None

async def revoke_gmail_credentials(user_id: str) -> None:
    """
    Revoke and remove stored Gmail credentials.
    
    Args:
        user_id: User's unique identifier
    """
    try:
        async with get_db() as db:
            gmail_creds = db.query(GmailCredentials).filter_by(user_id=user_id).first()
            
            if gmail_creds:
                # Load credentials to revoke them
                credentials = await load_gmail_credentials(user_id)
                if credentials:
                    # Build service and revoke
                    service = build('oauth2', 'v2', credentials=Credentials.from_authorized_user_info(credentials))
                    service._http.request(credentials.token_uri + '/revoke?token=' + credentials.token)
                
                # Remove from database
                db.delete(gmail_creds)
                await db.commit()
            
        logger.info(f"Gmail credentials revoked for user {user_id}")
    except Exception as e:
        logger.error(f"Error revoking credentials: {str(e)}")
        raise GmailError("Failed to revoke credentials")

async def check_gmail_auth(user_id: str) -> Dict[str, Any]:
    """
    Check Gmail authentication status.
    
    Args:
        user_id: User's unique identifier
    
    Returns:
        Dict containing authentication status and email if authenticated
    """
    try:
        async with get_db() as db:
            gmail_creds = db.query(GmailCredentials).filter_by(user_id=user_id).first()
            
            if not gmail_creds:
                return {'is_authenticated': False}
            
            # Load and verify credentials
            credentials = await load_gmail_credentials(user_id)
            if not credentials:
                return {'is_authenticated': False}
                
            return {
                'is_authenticated': True,
                'email': gmail_creds.email,
                'last_sync': gmail_creds.last_sync
            }
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}")
        return {'is_authenticated': False}

async def authenticator(user_id: Optional[str] = None, return_auth_url: bool = False, state: Optional[str] = None):
    """
    Authenticate with Gmail API.
    
    Args:
        user_id: User's unique identifier
        return_auth_url: If True, return the auth flow without running the local server
        state: Optional state token for verifying the callback
        
    Returns:
        Union[Resource, InstalledAppFlow]: Gmail service or auth flow depending on return_auth_url
    """
    try:
        if user_id and not return_auth_url:
            # Try to load existing credentials
            credentials = await load_gmail_credentials(user_id)
            if credentials:
                return build('gmail', 'v1', credentials=Credentials.from_authorized_user_info(credentials))
        
        # Create new flow
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json',
            SCOPES,
            state=state
        )
        
        if return_auth_url:
            return flow
            
        creds = flow.run_local_server(port=0)
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Gmail authentication error: {str(e)}")
        raise GmailError(f"Failed to authenticate with Gmail: {str(e)}")

def extract_body(message: Dict[str, Any]) -> str:
    """
    Extract and clean email body from Gmail message.
    
    Args:
        message: Gmail message object
        
    Returns:
        str: Cleaned email body text
        
    Raises:
        GmailError: If body extraction fails
    """
    try:
        body = ""
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8').strip()
                if part['mimeType'] == 'text/html':
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8').strip()
                    soup = BeautifulSoup(body, "html.parser")
                    body = soup.get_text()
        else:
            body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8').strip()
            if message['payload']['mimeType'] == 'text/html':
                soup = BeautifulSoup(body, "html.parser")
                body = soup.get_text()
        
        return body.strip()
        
    except Exception as e:
        logger.error(f"Error extracting email body: {str(e)}")
        raise GmailError(f"Failed to extract email body: {str(e)}")

def store_email(connection: mysql.connector.connection.MySQLConnection,
                sender: str,
                recipient: str,
                subject: str,
                body: str,
                sent_at: datetime,
                email_link: str) -> None:
    """
    Store email in the database with proper error handling.
    
    Args:
        connection: Database connection
        sender: Email sender
        recipient: Email recipient
        subject: Email subject
        body: Email body
        sent_at: Email timestamp
        email_link: Link to original email
        
    Raises:
        DatabaseConnectionError: If database operation fails
    """
    try:
        cursor = connection.cursor()
        
        # First, ensure user exists
        cursor.execute(
            "INSERT IGNORE INTO Users (email) VALUES (%s)",
            (recipient,)
        )
        connection.commit()
        
        # Get user_id
        cursor.execute(
            "SELECT id FROM Users WHERE email = %s",
            (recipient,)
        )
        user_id = cursor.fetchone()[0]
        
        # Store email
        cursor.execute("""
            INSERT INTO Email (sender, recipient, subject, body, sent_at, user_id, email_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (sender, recipient, subject, body, sent_at, user_id, email_link))
        
        connection.commit()
        cursor.close()
        
    except mysql.connector.Error as e:
        logger.error(f"Error storing email: {str(e)}")
        raise DatabaseConnectionError(f"Failed to store email: {str(e)}")

def get_last_month_emails(service) -> None:
    """
    Fetch and store last month's emails.
    
    Args:
        service: Gmail service object
        
    Raises:
        GmailError: If email fetching fails
        DatabaseConnectionError: If database operations fail
    """
    month = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')
    connection = None

    try:
        connection = get_db_connection()
        
        # Get unread emails from last month
        response = service.users().messages().list(
            userId='me',
            q=f'after:{month} is:unread'
        ).execute()
        
        messages = response.get('messages', [])
        if not messages:
            logger.info("No new emails found in the last month")
            return

        processed_count = 0
        error_count = 0
        
        for msg in messages:
            try:
                msg_id = msg['id']
                message = service.users().messages().get(userId='me', id=msg_id).execute()
                
                # Extract email data
                headers = message.get('payload', {}).get('headers', [])
                sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown Sender")
                subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
                date_str = next((header['value'] for header in headers if header['name'] == 'Date'), None)
                
                # Parse date with error handling
                try:
                    sent_at = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z') if date_str else datetime.now()
                except ValueError:
                    logger.warning(f"Invalid date format: {date_str}")
                    sent_at = datetime.now()
                
                # Get recipient
                profile = service.users().getProfile(userId='me').execute()
                receiver = profile['emailAddress']
                
                # Extract and clean body
                text = extract_body(message)
                
                # Create email link
                email_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{msg_id}+in%3Aall"
                
                # Store in database
                store_email(connection, sender, receiver, subject, text, sent_at, email_link)
                
                # Mark as processed in Gmail
                service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
                
                processed_count += 1
                logger.debug(f"Processed email: {subject[:50]}...")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing message {msg.get('id')}: {str(e)}")
                continue
        
        logger.info(f"Email processing completed. Processed: {processed_count}, Errors: {error_count}")
        
    except HttpError as e:
        logger.error(f"Gmail API error: {str(e)}")
        raise GmailError(f"Gmail API error: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise
        
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    try:
        service = authenticator()
        get_last_month_emails(service)
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        raise 