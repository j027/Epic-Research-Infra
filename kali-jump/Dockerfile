FROM kalilinux/kali-rolling:latest

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
    nmap \
    netcat-traditional \
    tcpdump \
    wireshark-common \
    hydra \
    john \
    hashcat \
    metasploit-framework \
    nikto \
    dirb \
    gobuster \
    sqlmap \
    && rm -rf /var/lib/apt/lists/*

# Create a user for SSH access (only if they don't exist)
RUN id student >/dev/null 2>&1 || (useradd -m -s /bin/bash student && \
    echo 'student:cybersec123' | chpasswd && \
    usermod -aG sudo student)

# Configure SSH
RUN mkdir -p /var/run/sshd && \
    echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config && \
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && \
    echo 'PubkeyAuthentication yes' >> /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A

# Set root password
RUN echo 'root:rootpass123' | chpasswd

# Create startup script that handles missing log files
RUN echo '#!/bin/bash' > /start.sh && \
    echo 'service ssh start' >> /start.sh && \
    echo 'touch /var/log/auth.log' >> /start.sh && \
    echo 'tail -f /var/log/auth.log' >> /start.sh && \
    chmod +x /start.sh

# Create a welcome message
RUN echo "echo 'Welcome to Kali Linux Jump Box - Cybersecurity Lab Environment'" >> /etc/bash.bashrc && \
    echo "echo 'Use this machine to access the internal Ubuntu targets'" >> /etc/bash.bashrc && \
    echo "echo 'Internal network: 172.20.0.0/24'" >> /etc/bash.bashrc && \
    echo "echo 'Ubuntu Target 1: ubuntu-target1 (172.20.0.11)'" >> /etc/bash.bashrc && \
    echo "echo 'Ubuntu Target 2: ubuntu-target2 (172.20.0.12)'" >> /etc/bash.bashrc

EXPOSE 22

CMD ["/start.sh"]
