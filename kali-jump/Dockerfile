FROM kalilinux/kali-rolling:latest

# Update and install essential packages
RUN apt-get update && apt-get install -y kali-linux-headless \
    && rm -rf /var/lib/apt/lists/*

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

# Create a welcome message
RUN echo "echo 'Welcome to Kali Linux Jump Box - Cybersecurity Lab Environment'" >> /etc/bash.bashrc && \
    echo "echo 'Use this machine to access the internal Ubuntu targets'" >> /etc/bash.bashrc && \
    echo "echo 'Internal network: 172.20.0.0/24'" >> /etc/bash.bashrc && \
    echo "echo 'Kali Jump Box: kali-jump (172.20.0.10)'" >> /etc/bash.bashrc && \
    echo "echo 'Ubuntu Target 1: ubuntu-target1 (172.20.0.11)'" >> /etc/bash.bashrc && \
    echo "echo 'Ubuntu Target 2: ubuntu-target2 (172.20.0.12)'" >> /etc/bash.bashrc && \
    echo "echo 'Please change your password after logging in for the first time.'" >> /etc/bash.bashrc

EXPOSE 22

CMD ["/usr/sbin/sshd","-D","-e"]
