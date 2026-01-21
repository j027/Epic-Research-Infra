FROM kalilinux/kali-last-release:latest

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install essential packages
RUN apt-get update && apt-get install -y \
    iputils-ping \
    iproute2 \
    metasploit-framework \
    nmap \
    libcap2-bin \
    nano \
    vim \
    openssh-server \
    expect \
    telnet \
    net-tools \
    man-db \ 
    sshpass \
    netcat-openbsd \
    distccd

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
RUN chmod +x /etc/update-motd.d/10-lab-info
RUN mkdir -p /etc/kali-motd && touch /etc/kali-motd/disable-all

EXPOSE 22

CMD ["/usr/sbin/sshd","-D","-e"]
