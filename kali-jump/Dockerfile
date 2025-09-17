FROM kalilinux/kali-rolling:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install essential packages
RUN apt-get update && apt-get install -y kali-linux-headless

# Install ping
RUN apt-get install iputils-ping

# Create a user for SSH access (only if they don't exist)
RUN id student >/dev/null 2>&1 || (useradd -m -s /bin/bash student && \
    echo 'student:student123' | chpasswd && \
    usermod -aG sudo student)

# configure ssh
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port .*/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Copy and setup the dynamic MOTD script
COPY 10-lab-info /etc/update-motd.d/10-lab-info
RUN chmod +x /etc/update-motd.d/10-lab-info && \
    chmod -x /etc/update-motd.d/00-header 2>/dev/null || true && \
    chmod -x /etc/update-motd.d/10-help-text 2>/dev/null || true && \
    chmod -x /etc/update-motd.d/50-motd-news 2>/dev/null || true && \
    chmod -x /etc/update-motd.d/80-esm 2>/dev/null || true && \
    chmod -x /etc/update-motd.d/95-hwe-eol 2>/dev/null || true

EXPOSE 22

CMD ["/usr/sbin/sshd","-D","-e"]
