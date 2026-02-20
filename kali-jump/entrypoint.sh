#!/bin/bash
# Entrypoint script for kali-jump container
# If STUDENT_PASSWORD is set (lab manager deployment), change the student password.
# If not set (standalone docker-compose), keep the default password (student123).

if [ -n "$STUDENT_PASSWORD" ]; then
    echo "student:$STUDENT_PASSWORD" | chpasswd
    unset STUDENT_PASSWORD
fi

# Start SSH daemon
exec /usr/sbin/sshd -D -e
