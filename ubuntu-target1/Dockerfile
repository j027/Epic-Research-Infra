FROM ubuntu:latest

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
    apache2 \
    mysql-server \
    php \
    php-mysql \
    vsftpd \
    telnetd \
    && rm -rf /var/lib/apt/lists/*

# Create users for SSH access (only if they don't exist)
RUN id student >/dev/null 2>&1 || (useradd -m -s /bin/bash student && \
    echo 'student:student123' | chpasswd && \
    usermod -aG sudo student)

RUN id admin >/dev/null 2>&1 || (useradd -m -s /bin/bash admin && \
    echo 'admin:admin456' | chpasswd && \
    usermod -aG sudo admin)

RUN id user1 >/dev/null 2>&1 || (useradd -m -s /bin/bash user1 && \
    echo 'user1:password' | chpasswd)

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config && \
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && \
    echo 'PubkeyAuthentication yes' >> /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Set root password
RUN echo 'root:toor' | chpasswd

# Configure Apache with a simple vulnerable web page
RUN echo '<?php if(isset($_GET["cmd"])) { system($_GET["cmd"]); } ?>' > /var/www/html/vulnerable.php && \
    echo '<html><body><h1>Ubuntu Target 1 - Web Server</h1><p>This is a practice target for cybersecurity exercises.</p></body></html>' > /var/www/html/index.html

# Configure FTP
RUN echo "anonymous_enable=YES" >> /etc/vsftpd.conf && \
    echo "local_enable=YES" >> /etc/vsftpd.conf && \
    echo "write_enable=YES" >> /etc/vsftpd.conf

# Create some interesting files for discovery
RUN mkdir -p /home/student/secrets && \
    echo "flag{ubuntu_target_1_user_directory}" > /home/student/secrets/flag.txt && \
    echo "backup_password=backup123" > /home/admin/.backup_creds && \
    chmod 600 /home/admin/.backup_creds && \
    chown admin:admin /home/admin/.backup_creds

# Create startup script
RUN echo '#!/bin/bash' > /start.sh && \
    echo 'service ssh start' >> /start.sh && \
    echo 'service apache2 start' >> /start.sh && \
    echo 'service vsftpd start' >> /start.sh && \
    echo 'touch /var/log/auth.log' >> /start.sh && \
    echo 'tail -f /var/log/auth.log' >> /start.sh && \
    chmod +x /start.sh

EXPOSE 22 80 21

CMD ["/start.sh"]
