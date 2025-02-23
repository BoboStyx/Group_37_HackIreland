#!./venv/bin/python
import mysql.connector
from typing import List, Dict, Any
import tiktoken

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except:
        # Fallback: rough estimation if tiktoken not available
        return len(text.split()) * 2

def db_to_ai() -> List[Dict[str, Any]]:
    """Get emails from database with limits on count and tokens."""
    DB_NAME = 'emails_db'
    DB_USER = 'Seyi'
    DB_PASSWORD = 'S1906@duposiDCU'
    DB_HOST = 'localhost'
    MAX_EMAILS = 50
    MAX_TOKENS = 50000

    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = connection.cursor(dictionary=True)

        # Get most recent emails first
        cursor.execute("SELECT * FROM Email ORDER BY sent_at DESC")
        records = cursor.fetchall()

        email_list = []
        total_tokens = 0

        for row in records:
            email_dict = dict(row)
            # Count tokens in subject and body
            email_text = f"{email_dict['subject']} {email_dict['body']}"
            email_tokens = count_tokens(email_text)
            
            if len(email_list) >= MAX_EMAILS or total_tokens + email_tokens > MAX_TOKENS:
                break
                
            total_tokens += email_tokens
            email_list.append(email_dict)

        # Clear processed emails
        email_ids = [email['id'] for email in email_list]
        if email_ids:
            cursor.execute(f"DELETE FROM Email WHERE id IN ({','.join(map(str, email_ids))})")
            connection.commit()

        cursor.close()
        connection.close()
        return email_list

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []

if __name__ == "__main__":
    emails = db_to_ai()
    print(emails)

# [{'id': 1, 'sender': 'alice@example.com', 'recipient': 'bob@example.com', 'subject': 'Meeting Reminder', 'body': 'Reminder for our meeting at 10 AM.', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 1, 'email_link': 'https://mail.google.com/mail/u/0/#search/rfc822msgid:1234567890+in%3Aall'},
#  {'id': 2, 'sender': 'bob@example.com', 'recipient': 'charlie@example.com', 'subject': 'Project Update', 'body': 'The deadline has been extended.', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 2, 'email_link': 'https://outlook.office.com/mail/search/id/1234567890'},
#  {'id': 3, 'sender': 'alice@example.com', 'recipient': 'dave@example.com', 'subject': 'Lunch Plans', 'body': 'Are we still on for lunch tomorrow?', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 1, 'email_link': 'https://mail.google.com/mail/u/0/#search/rfc822msgid:1234567890+in%3Aall'}]
