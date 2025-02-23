#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check Python version
if ! command_exists python3; then
    print_message $RED "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_message $YELLOW "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_message $GREEN "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
print_message $YELLOW "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_message $YELLOW "Creating .env file from example..."
    cp .env.example .env
    print_message $RED "Please update the .env file with your configuration before continuing."
    exit 1
fi

# Function to start the API server
start_server() {
    print_message $GREEN "Starting API server..."
    # Use python -m uvicorn to ensure module imports work correctly
    python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!
    
    # Wait for server to start
    print_message $YELLOW "Waiting for server to start..."
    sleep 5
}

# Function to stop the API server
stop_server() {
    if [ ! -z "$SERVER_PID" ]; then
        print_message $YELLOW "Stopping API server..."
        kill $SERVER_PID
        # Also kill any remaining uvicorn processes
        pkill -f "uvicorn api:app"
    fi
}

# Function to run manual tests
run_tests() {
    print_message $GREEN "Running system tests..."
    python test_system.py
}

# Function to run individual components
test_component() {
    local component=$1
    case $component in
        "email")
            print_message $GREEN "Testing email processing..."
            python get_mail.py
            ;;
        "tasks")
            print_message $GREEN "Testing task management..."
            curl -X GET "http://localhost:8000/tasks"
            echo # Add newline after curl output
            ;;
        "process")
            print_message $GREEN "Testing input processing..."
            curl -X POST "http://localhost:8000/process" \
                -H "Content-Type: application/json" \
                -d '{"text": "Create a high priority task for testing", "context": {"urgency": "high"}}'
            echo # Add newline after curl output
            ;;
        "health")
            print_message $GREEN "Testing API health..."
            curl -X GET "http://localhost:8000/health"
            echo # Add newline after curl output
            ;;
        *)
            print_message $RED "Unknown component: $component"
            print_message $YELLOW "Available components: email, tasks, process, health"
            ;;
    esac
}

# Cleanup function
cleanup() {
    print_message $YELLOW "Cleaning up..."
    stop_server
    deactivate
}

# Set up trap to ensure cleanup on script exit
trap cleanup EXIT

# Handle command line arguments
case "$1" in
    "server")
        start_server
        # Keep script running
        while true; do sleep 1; done
        ;;
    "test")
        start_server
        run_tests
        ;;
    "component")
        if [ -z "$2" ]; then
            print_message $RED "Please specify a component to test"
            print_message $YELLOW "Usage: ./test.sh component [email|tasks|process|health]"
            exit 1
        fi
        start_server
        test_component $2
        ;;
    *)
        print_message $YELLOW "Usage: ./test.sh [server|test|component]"
        print_message $YELLOW "  server    - Start the API server"
        print_message $YELLOW "  test      - Run all system tests"
        print_message $YELLOW "  component - Test specific component (email|tasks|process|health)"
        exit 1
        ;;
esac 