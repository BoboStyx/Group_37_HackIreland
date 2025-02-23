from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64
import mysql.connector
from bs4 import BeautifulSoup

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticator():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('gmail', 'v1', credentials=creds)

def body(message):
    body_text = ""
    if 'parts' in message['payload']:
        for eachpart in message['payload']['parts']:
            if eachpart['mimeType'] == 'text/plain':
                body_text = " ".join(base64.urlsafe_b64decode(eachpart['body']['data']).decode('utf-8').split())
            if eachpart['mimeType'] == 'text/html':
                body_text = " ".join(base64.urlsafe_b64decode(eachpart['body']['data']).decode('utf-8').split())
                soup = BeautifulSoup(body_text, "html.parser")
                body_text = soup.get_text()
    else:
        body_text = " ".join(base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8').split())
        if message['payload']['mimeType'] == 'text/html':
            soup = BeautifulSoup(body_text, "html.parser")
            body_text = soup.get_text()
    return body_text 

def insert_into_db(sender, recipient, subject, body, sent_at, emaillink):
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Krishnasiri924!',
            database='emails_db',
            auth_plugin='mysql_native_password'  
        )
        cursor = connection.cursor()

        sql = """
        INSERT INTO Email (user_id, sender, recipient, subject, body, sent_at, link)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (1, sender, recipient, subject, body, sent_at, emaillink))
        connection.commit()

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_last_month_senders(service):
    month = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')
    next_page_token = None  # Start with no page token

    while True:
        response = service.users().messages().list(
            userId='me',
            q=f'after:{month} is:unread',  # Modify query as needed
            maxResults=100,  # Fetch 100 emails per request
            pageToken=next_page_token  # Pass the nextPageToken if available
        ).execute()

        messages = response.get('messages', [])

        if not messages:
            print("No more emails found.")
            break  # Stop if no messages are returned

        for msg in messages: 
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id).execute()

            headers = message.get('payload', {}).get('headers', [])

            emaillink = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"
            sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown Sender")
            subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
            date = next((header['value'] for header in headers if header['name'] == 'Date'))
            profile = service.users().getProfile(userId='me').execute()
            receiver = profile['emailAddress']
            text = body(message)

            # Process date into MySQL format
            try:
                sent_at = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert into database
            insert_into_db(sender, receiver, subject, text, sent_at, emaillink)

        next_page_token = response.get('nextPageToken')  # Get the token for the next batch
        if not next_page_token:
            break  # Stop if there's no more data to fetch



service = authenticator()
get_last_month_senders(service)

