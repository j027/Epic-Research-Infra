FROM ubuntu:24.04

RUN apt-get update
RUN apt-get install -y openssh-server distcc supervisor build-essential sudo iproute2 man-db 
RUN rm -rf /var/lib/apt/lists/*

# copy supervisor configuration files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY supervisor.d/*.conf /etc/supervisor/conf.d/

RUN useradd -m -s /bin/bash distcc && \
    mkdir -p /etc/sudoers.d && \
    echo "distcc ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/distcc && \
    chmod 0440 /etc/sudoers.d/distcc

RUN useradd -m -s /bin/bash labuser && \
    echo 'labuser:defendlab | chpasswd && \
    usermod -aG sudo labuser

# configure ssh
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port .*/Port 22/' /etc/ssh/sshd_config && \
    ssh-keygen -A


EXPOSE 22 3632

ENTRYPOINT ["/usr/bin/supervisord"]