from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64
from bs4 import BeautifulSoup

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticator():
    """Authenticates with Gmail API and returns a service object."""
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

def get_last_month_senders(service):
    """Fetches eFmails from the last month and prints sender information."""
    month = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')

    response = service.users().messages().list(userId='me', q=f'after:{month} is:unread').execute()
    messages = response.get('messages', [])

    if not messages:
        print("No emails found in the last month.")
        return

    print("\n--- Senders of Emails from the Last Month ---\n")
    for msg in messages: 
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()

        # Extract sender from email headers
        headers = message.get('payload', {}).get('headers', [])
        sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown Sender")
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
        date = next((header['value'] for header in headers if header['name'] == 'Date'))
        text = body(message)



        #print(sender)
        #print(subject)
        #print(text)
        print(date)

# Authenticate and fetch senders
service = authenticator()
get_last_month_senders(service)
