#!/bin/bash

# Create flag from environment variables
# This runs once at container startup and creates the challenge file

# Set defaults if environment variables are not provided (use default when unset or empty)
FLAG_CONTENT="${FLAG_CONTENT:-f4k3_fl4g_f0r_t3st1ng}"
ZIP_PASSWORD="${ZIP_PASSWORD:-maggie}"
FLAG_LOCATION="${FLAG_LOCATION:-/var/log/asdfgnarlyzxcv.zip}"

# Create the flag file
echo "Creating lab challenge flag..."
echo "$FLAG_CONTENT" > /tmp/flag.txt

# Create password-protected zip file
zip -P "$ZIP_PASSWORD" "$FLAG_LOCATION" /tmp/flag.txt

# Clean up temporary files (remove traces)
rm -f /tmp/flag.txt

echo "Flag challenge created at: $FLAG_LOCATION"

# Clear environment variables for security (overwrite then unset)
FLAG_CONTENT=""
ZIP_PASSWORD=""
FLAG_LOCATION=""
unset FLAG_CONTENT ZIP_PASSWORD FLAG_LOCATION
# Delete self to prevent students from finding the script
rm -f "$0"

# Hand off to supervisord as the main process so this script is the entrypoint
echo "Starting supervisord..."
exec /usr/bin/supervisord -n