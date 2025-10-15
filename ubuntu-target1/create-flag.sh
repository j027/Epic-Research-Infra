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
zip -j -P "$ZIP_PASSWORD" "$FLAG_LOCATION" /tmp/flag.txt

# Clean up temporary files (remove traces)
rm -f /tmp/flag.txt

echo "Flag challenge created at: $FLAG_LOCATION"

# Clear environment variables for security (overwrite then unset)
FLAG_CONTENT=""
ZIP_PASSWORD=""
FLAG_LOCATION=""
unset FLAG_CONTENT ZIP_PASSWORD FLAG_LOCATION

# Replace this script with a simple supervisord launcher
# This prevents students from finding the flag creation logic
# while keeping the entrypoint intact
cat > "$0" << 'EOF'
#!/bin/bash
# Supervisord launcher - flag has already been created
exec /usr/bin/supervisord -n
EOF

chmod +x "$0"

# Hand off to supervisord as the main process so this script is the entrypoint
echo "Starting supervisord..."
exec /usr/bin/supervisord -n