-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS emails_db;
USE emails_db;

-- Create Users table
CREATE TABLE IF NOT EXISTS Users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Email table
CREATE TABLE IF NOT EXISTS Email (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMP,
    user_id INT,
    email_link VARCHAR(512),
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id)
);

-- Create Tasks table
CREATE TABLE IF NOT EXISTS Tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    urgency INT CHECK (urgency BETWEEN 1 AND 5),
    due_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    email_id INT,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES Email(id),
    FOREIGN KEY (user_id) REFERENCES Users(id)
);

-- Create Opportunities table
CREATE TABLE IF NOT EXISTS Opportunities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    relevance INT CHECK (relevance BETWEEN 0 AND 100),
    email_id INT,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES Email(id),
    FOREIGN KEY (user_id) REFERENCES Users(id)
); 