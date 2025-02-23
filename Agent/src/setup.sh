#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_message $RED "This script is designed for macOS. Please modify it for your OS."
    exit 1
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    print_message $YELLOW "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

# Install system dependencies using Homebrew
print_message $YELLOW "Installing system dependencies..."
brew install mysql python@3.11 rust cmake

# Start MySQL service
if ! brew services list | grep mysql | grep started > /dev/null; then
    print_message $YELLOW "Starting MySQL service..."
    brew services start mysql
    
    print_message $YELLOW "Setting up MySQL root password..."
    mysql_secure_installation
fi

# Create and activate virtual environment
print_message $YELLOW "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Set up environment variables for compilation
export LDFLAGS="-L/opt/homebrew/opt/openssl@3/lib"
export CPPFLAGS="-I/opt/homebrew/opt/openssl@3/include"
export PKG_CONFIG_PATH="/opt/homebrew/opt/openssl@3/lib/pkgconfig"
export MAKEFLAGS="-j$(sysctl -n hw.ncpu)"

# Upgrade pip and install wheel
print_message $YELLOW "Upgrading pip and installing wheel..."
pip install --upgrade pip wheel setuptools

# Install key dependencies first
print_message $YELLOW "Installing key dependencies..."
pip install --no-cache-dir pydantic tiktoken

# Install remaining dependencies
print_message $YELLOW "Installing remaining dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_message $YELLOW "Creating .env file..."
    cat > .env << EOL
# Environment
ENVIRONMENT=development

# Server Settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_TIMEOUT=60

# Database Configuration
DEV_DB_HOST=localhost
DEV_DB_USER=root
DEV_DB_PASSWORD=your_mysql_root_password
DEV_DB_NAME=ai_agent_dev
DEV_DB_PORT=3306

# API Keys
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
O3_MINI_API_KEY=your_o3_key_here

# Model Settings
GEMINI_TEMPERATURE=0.7
GEMINI_TOP_K=40
GEMINI_TOP_P=0.95
GEMINI_MAX_TOKENS=1024

# Processing Limits
MAX_EMAILS=50
MAX_TOKENS=50000
EOL
    print_message $RED "Please update the .env file with your API keys and MySQL root password."
fi

# Create MySQL database and user if they don't exist
print_message $YELLOW "Setting up MySQL database..."
read -sp "Enter MySQL root password: " MYSQL_ROOT_PASSWORD
echo

mysql -u root -p"$MYSQL_ROOT_PASSWORD" << EOF
CREATE DATABASE IF NOT EXISTS ai_agent_dev;
CREATE USER IF NOT EXISTS 'dev_user'@'localhost' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON ai_agent_dev.* TO 'dev_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# Make test script executable
chmod +x test.sh

print_message $GREEN "Setup complete! Next steps:"
print_message $YELLOW "1. Update the .env file with your:"
print_message $YELLOW "   - MySQL root password"
print_message $YELLOW "   - API keys (OpenAI, Gemini, O3)"
print_message $YELLOW "2. Run the server: ./test.sh server"
print_message $YELLOW "3. Run tests: ./test.sh test"
print_message $YELLOW "4. Test components: ./test.sh component [name]" 