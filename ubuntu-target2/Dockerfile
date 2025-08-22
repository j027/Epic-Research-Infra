FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install essential packages
RUN apt-get update && apt-get install -y \
    openssh-server \
    sudo \
    nano \
    vim \
    curl \
    wget \
    net-tools \
    iputils-ping \
    nginx \
    postgresql \
    postgresql-contrib \
    python3 \
    python3-pip \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create users for SSH access (only if they don't exist)
RUN id student >/dev/null 2>&1 || (useradd -m -s /bin/bash student && \
    echo 'student:student456' | chpasswd && \
    usermod -aG sudo student)

RUN id developer >/dev/null 2>&1 || (useradd -m -s /bin/bash developer && \
    echo 'developer:dev123' | chpasswd && \
    usermod -aG sudo developer)

RUN id backup >/dev/null 2>&1 || (useradd -m -s /bin/bash backup && \
    echo 'backup:backup789' | chpasswd)

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config && \
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && \
    echo 'PubkeyAuthentication yes' >> /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Set root password
RUN echo 'root:ubuntu' | chpasswd

# Configure Nginx with a simple web page
RUN echo '<html><body><h1>Ubuntu Target 2 - Development Server</h1><p>This server contains development resources and databases.</p></body></html>' > /var/www/html/index.html

# Set up PostgreSQL
USER postgres
RUN /etc/init.d/postgresql start && \
    psql --command "CREATE USER dbuser WITH SUPERUSER PASSWORD 'dbpass123';" && \
    createdb -O dbuser testdb

USER root

# Create some interesting files for discovery
RUN mkdir -p /home/developer/projects && \
    echo "flag{ubuntu_target_2_database_server}" > /home/developer/projects/flag.txt && \
    echo "database_url=postgresql://dbuser:dbpass123@localhost/testdb" > /home/developer/.env && \
    echo "api_key=sk-1234567890abcdef" >> /home/developer/.env && \
    chmod 600 /home/developer/.env && \
    chown developer:developer /home/developer/.env

# Create a simple Node.js app
RUN mkdir -p /home/developer/webapp && \
    echo '{"name": "vulnerable-app", "version": "1.0.0", "main": "app.js"}' > /home/developer/webapp/package.json && \
    echo 'const express = require("express"); const app = express(); app.get("/", (req, res) => { res.send("Development Web App"); }); app.listen(3000);' > /home/developer/webapp/app.js && \
    chown -R developer:developer /home/developer/webapp

# Create startup script
RUN echo '#!/bin/bash' > /start.sh && \
    echo 'service ssh start' >> /start.sh && \
    echo 'service nginx start' >> /start.sh && \
    echo 'service postgresql start' >> /start.sh && \
    echo 'touch /var/log/auth.log' >> /start.sh && \
    echo 'tail -f /var/log/auth.log' >> /start.sh && \
    chmod +x /start.sh

EXPOSE 22 80 5432 3000

CMD ["/start.sh"]
