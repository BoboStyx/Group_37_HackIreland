'''

import mysql.connector
from mysql.connector import errorcode

# Database connection settings
DB_NAME = 'your_database'
DB_USER = 'your_username'
DB_PASSWORD = 'your_password'
DB_HOST = 'localhost'

# Connect to MySQL and create the database if it doesn't exist
try:
    conn = mysql.connector.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")

    conn.database = DB_NAME

    # Create the User table
    create_table_query = """
        CREATE TABLE IF NOT EXISTS User (
            id INT AUTO_INCREMENT PRIMARY KEY,
            description TEXT NOT NULL,
            urgency INT CHECK (urgency BETWEEN 1 AND 5),
            status ENUM('pending', 'half-completed', 'completed'),
            alertAt DATETIME,
            TimeEmailSent DATETIME
        )
    """
    cursor.execute(create_table_query)

    # Insert sample data
    sample_data = [
        ("Follow up on project proposal", 5, "pending", "2025-02-25 10:00:00", "2025-02-20 14:00:00"),
        ("Prepare for client meeting", 4, "half-completed", "2025-02-23 09:00:00", "2025-02-19 13:00:00")
    ]

    insert_query = """
        INSERT INTO User (description, urgency, status, alertAt, TimeEmailSent)
        VALUES (%s, %s, %s, %s, %s)
    """

    cursor.executemany(insert_query, sample_data)

    conn.commit()
    cursor.close()
    conn.close()
    print("Database and table created, data inserted successfully!")

except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Something is wrong with your username or password")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Database does not exist")
    else:
        print(err)
'''

#Edit as please, above was just sample code.