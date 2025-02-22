import mysql.connector


try:
    connection = mysql.connector.connect(
        host='localhost',
        user='Seyi',
        password='S1906@duposiDCU',
        database='emails_db'
    )
    print("Connected successfully!")
except mysql.connector.Error as err:
    print(f"Error: {err}")
finally:
    if connection.is_connected():

        cursor = connection.cursor()
        cursor.execute("SELECT * FROM User")

        for row in cursor.fetchall():
            print(row)
        cursor.close()
        connection.close()
        print("MySQL connection is closed")   
  
