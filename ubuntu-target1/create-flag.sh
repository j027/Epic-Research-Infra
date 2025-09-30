#!/bin/bash

# Create flag from environment variables
# This runs once at container startup and creates the challenge file

# Set defaults if environment variables are not provided
FLAG_CONTENT="${FLAG_CONTENT}"
ZIP_PASSWORD="${ZIP_PASSWORD}"
FLAG_LOCATION="${FLAG_LOCATION}"

# Create the flag file
echo "Creating lab challenge flag..."
echo "$FLAG_CONTENT" > /tmp/flag.txt

# Create password-protected zip file
zip -P "$ZIP_PASSWORD" "$FLAG_LOCATION" /tmp/flag.txt

# Clean up temporary files (remove traces)
rm -f /tmp/flag.txt

echo "Flag challenge created at: $FLAG_LOCATION"

# Clear environment variables for security
unset FLAG_CONTENT
unset ZIP_PASSWORD
unset FLAG_LOCATION

# Delete self to prevent students from finding the script
rm -f "$0"