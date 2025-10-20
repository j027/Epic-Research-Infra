#!/bin/bash

# Create flag from environment variables
# This runs once at container startup and creates the challenge file
# Uses a marker file to ensure flag is only created once

# Set defaults if environment variables are not provided (use default when unset or empty)
FLAG_CONTENT="${FLAG_CONTENT:-f4k3_fl4g_f0r_t3st1ng}"
ZIP_PASSWORD="${ZIP_PASSWORD:-maggie}"
FLAG_LOCATION="${FLAG_LOCATION:-/var/log/asdfgnarlyzxcv.zip}"
MARKER_FILE="/var/.flag_created"

# Only create flag if marker file doesn't exist
if [ ! -f "$MARKER_FILE" ]; then
    # Create the flag file
    echo "Creating lab challenge flag..."
    echo "$FLAG_CONTENT" > /tmp/flag.txt

    # Create password-protected zip file
    zip -j -P "$ZIP_PASSWORD" "$FLAG_LOCATION" /tmp/flag.txt

    # Clean up temporary files (remove traces)
    rm -f /tmp/flag.txt

    echo "Flag challenge created at: $FLAG_LOCATION"
    
    # Create marker file to prevent recreation on restart
    touch "$MARKER_FILE"
else
    echo "Flag already exists, skipping creation..."
fi

# Clear environment variables for security (overwrite then unset)
FLAG_CONTENT=""
ZIP_PASSWORD=""
FLAG_LOCATION=""
unset FLAG_CONTENT ZIP_PASSWORD FLAG_LOCATION

# Hand off to supervisord as the main process
echo "Starting supervisord..."
exec /usr/bin/supervisord -n