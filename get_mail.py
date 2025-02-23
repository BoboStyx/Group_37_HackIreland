from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64
from bs4 import BeautifulSoup
import mysql.connector
from config import DATABASE_CONFIG

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_db_connection():
    """Create a database connection."""
    config = DATABASE_CONFIG['production']
    return mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database']
    )

def authenticator():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('gmail', 'v1', credentials=creds)

def body(message):
    body = ""
    if 'parts' in message['payload']:
        for eachpart in message['payload']['parts']:
            if eachpart['mimeType'] == 'text/plain':
                body = base64.urlsafe_b64decode(eachpart['body']['data']).decode('utf-8').strip()
            if eachpart['mimeType'] == 'text/html':
                body = base64.urlsafe_b64decode(eachpart['body']['data']).decode('utf-8').strip()
                soup = BeautifulSoup(body, "html.parser")
                body = soup.get_text()
        
    else:
        body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8').strip()
        if message['payload']['mimeType'] == 'text/html':
            soup = BeautifulSoup(body, "html.parser")
            body = soup.get_text()
    
    return body 

def store_email(connection, sender, recipient, subject, body, sent_at, email_link):
    """Store email in the database."""
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

def get_last_month_senders(service):
    """Fetch last month's emails and store them in the database."""
    month = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')

    try:
        connection = get_db_connection()
        
        response = service.users().messages().list(userId='me', q=f'after:{month} is:unread').execute()
        messages = response.get('messages', [])

        if not messages:
            print("No emails found in the last month.")
            return

        for msg in messages: 
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            
            # Extract email data
            sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown Sender")
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
            date_str = next((header['value'] for header in headers if header['name'] == 'Date'), None)
            sent_at = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z') if date_str else datetime.now()
            profile = service.users().getProfile(userId='me').execute()
            receiver = profile['emailAddress']
            text = body(message)
            
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
        
        connection.close()
        print("Email processing completed successfully.")
        
    except Exception as e:
        print(f"Error processing emails: {str(e)}")
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    service = authenticator()
    get_last_month_senders(service)
