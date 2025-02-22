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
        cursor = connection.cursor(dictionary=True)  # Correct indentation

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

db_to_ai()
