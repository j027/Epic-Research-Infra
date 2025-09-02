FROM ubuntu:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install essential packages
RUN apt-get update && apt-get install -y \
    openssh-server \
    supervisor \
    sudo \
    nano \
    vim \
    curl \
    wget \
    net-tools \
    iputils-ping \
    nginx

# Create users for SSH access (only if they don't exist)
RUN id student >/dev/null 2>&1 || (useradd -m -s /bin/bash student && \
    echo 'student:student123' | chpasswd && \
    usermod -aG sudo student)

# configure ssh
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port .*/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Create a simple Nginx hello page
RUN echo '<html><body><h1>Ubuntu Target 2 - Nginx Server</h1><p>This is the second Ubuntu target machine running Nginx.</p><p>Use supervisorctl to manage services.</p></body></html>' > /var/www/html/index.html

# Configure supervisord
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 22 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
