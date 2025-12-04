# pinned to the latest build as of 9/18/2025
# to prevent things from breaking
FROM heywoodlh/vulnerable@sha256:a608b548838c2bb947d62ee9e9a97bd7ef966c8ab0e27cbf6bddf5e55b578189

# Install zip utility for flag creation and telnet server
RUN apt-get update && apt-get install -y zip sshpass xinetd telnetd && rm -rf /var/lib/apt/lists/*

##ProFTPD
EXPOSE 21
## OpenSSH
EXPOSE 22
## Telnet
EXPOSE 23
## HTTP
EXPOSE 80
## Samba
EXPOSE 445
## CUPS 
EXPOSE 631
## Chatbot 
EXPOSE 3000
## Readme_app
EXPOSE 3500
## UnrealIRC
EXPOSE 6667
## MySQL
EXPOSE 3306
## Sinatra
EXPOSE 8181

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY supervisor.d/*.conf /etc/supervisor/conf.d/
COPY start.sh /start.sh
COPY telnet /etc/xinetd.d/telnet
COPY issue.net /etc/issue.net

# add Army Week plans to hidden directory
RUN mkdir -p /home/msfadmin/.secret/.plans/
COPY Army_Week_Plans.txt /home/msfadmin/.secret/.plans/Army_Week_Plans.txt

# Create msfadmin user with password 'msfadmin' for both telnet and SSH access
RUN useradd -m -s /bin/bash msfadmin && \
    echo 'msfadmin:msfadmin' | chpasswd && \
    usermod -aG sudo msfadmin

ENTRYPOINT ["/usr/bin/supervisord"]
