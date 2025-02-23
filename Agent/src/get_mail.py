"""
Gmail integration for fetching and processing emails.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import base64
from bs4 import BeautifulSoup
import mysql.connector
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from server_config import server_config, db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not server_config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

def authenticator():
    """
    Authenticate with Gmail API.
    
    Returns:
        googleapiclient.discovery.Resource: Gmail service
        
    Raises:
        GmailError: If authentication fails
    """
    try:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
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