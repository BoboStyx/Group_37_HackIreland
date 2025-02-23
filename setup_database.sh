#!/bin/bash

# Default values
DB_NAME="ai_agent"
DB_USER="root"
PASSWORD_PARAM=""

# Parse command line arguments
while getopts "n:u:p" opt; do  # Removed : after p
  case $opt in
    n) DB_NAME="$OPTARG"
    ;;
    u) DB_USER="$OPTARG"
    ;;
    p) PASSWORD_PARAM="-p"  # Just use -p to prompt for password
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done

# Create database if it doesn't exist
echo "Creating database $DB_NAME if it doesn't exist..."
mysql -u "$DB_USER" $PASSWORD_PARAM -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"

# Import the SQL file
echo "Importing dummy data..."
mysql -u "$DB_USER" $PASSWORD_PARAM "$DB_NAME" < init_dummy_data.sql

echo "Database setup complete!"
echo "You can now update your .env file with:"
echo "DATABASE_URL=mysql://$DB_USER:PASSWORD@localhost/$DB_NAME" 