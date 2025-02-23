#!/usr/bin/env python3
"""
Setup script for the email processing system.
This script will:
1. Create the database and tables
2. Install required dependencies
3. Check for required credentials
"""
import os
import sys
import subprocess
import mysql.connector
from config import DATABASE_CONFIG

def install_requirements():
    """Install required Python packages."""
    requirements = [
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client',
        'beautifulsoup4',
        'mysql-connector-python',
        'tiktoken',
        'sqlalchemy',
        'python-dotenv',
        'fastapi',
        'uvicorn'
    ]
    
    print("Installing required packages...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + requirements)
    print("Package installation completed.")

def setup_database():
    """Set up the database using the schema."""
    config = DATABASE_CONFIG['production']
    
    try:
        # First connect without database to create it
        connection = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        cursor = connection.cursor()
        
        # Read and execute schema
        with open('schema.sql', 'r') as f:
            sql_commands = f.read().split(';')
            for command in sql_commands:
                if command.strip():
                    cursor.execute(command + ';')
        
        connection.commit()
        print("Database setup completed successfully.")
        
    except mysql.connector.Error as err:
        print(f"Error setting up database: {err}")
        sys.exit(1)
    finally:
        if 'connection' in locals():
            cursor.close()
            connection.close()

def check_credentials():
    """Check if required credential files exist."""
    required_files = [
        'credentials.json'  # Google API credentials
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print("Missing required credential files:")
        for file in missing_files:
            print(f"- {file}")
        print("\nPlease ensure these files are present before running the system.")
        sys.exit(1)
    
    print("All required credential files found.")

def main():
    """Main setup function."""
    print("Starting setup...")
    
    # Install requirements
    install_requirements()
    
    # Check credentials
    check_credentials()
    
    # Set up database
    setup_database()
    
    print("\nSetup completed successfully!")
    print("""
Next steps:
1. Ensure your Google API credentials are properly configured in credentials.json
2. Run get_mail.py to fetch emails
3. Run process_emails.py to process the fetched emails
""")

if __name__ == "__main__":
    main() 