import mysql.connector

def db_to_ai():
    DB_NAME = 'emails_db'
    DB_USER = 'Seyi'
    DB_PASSWORD = 'S1906@duposiDCU'
    DB_HOST = 'localhost'

    data = {}

    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        cursor = connection.cursor(dictionary=True)  

        cursor.execute("SELECT * FROM Email")
        records = cursor.fetchall()

        email_list = [dict(row) for row in records]        

        cursor.execute("TRUNCATE TABLE Email")
        connection.commit()
        cursor.close()
        connection.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    return email_list
# [{'id': 1, 'sender': 'alice@example.com', 'recipient': 'bob@example.com', 'subject': 'Meeting Reminder', 'body': 'Reminder for our meeting at 10 AM.', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 1},
#  {'id': 2, 'sender': 'bob@example.com', 'recipient': 'charlie@example.com', 'subject': 'Project Update', 'body': 'The deadline has been extended.', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 2},
#  {'id': 3, 'sender': 'alice@example.com', 'recipient': 'dave@example.com', 'subject': 'Lunch Plans', 'body': 'Are we still on for lunch tomorrow?', 'sent_at': datetime.datetime(2025, 2, 22, 21, 56, 36), 'user_id': 1}]

db_to_ai()
