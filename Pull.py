import mysql.connector

DB_NAME = 'emails_db'
DB_USER = 'Seyi'
DB_PASSWORD = 'S1906@duposiDCU'
DB_HOST = 'localhost'

try:
    connection = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM User")
    records = cursor.fetchall()

    for row in records:
        print(row)

    cursor.close()
    connection.close()

except mysql.connector.Error as err:
    print(f"Error: {err}")