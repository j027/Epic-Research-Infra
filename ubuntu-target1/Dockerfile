# pinned to the latest build as of 9/18/2025
# to prevent things from breaking
FROM heywoodlh/vulnerable@sha256:a608b548838c2bb947d62ee9e9a97bd7ef966c8ab0e27cbf6bddf5e55b578189

# delete the user with a weak password
RUN userdel -r vuln

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
COPY start.sh /start.sh
COPY create-flag.sh /create-flag.sh
COPY telnet /etc/xinetd.d/telnet
COPY issue.net /etc/issue.net

# Make scripts executable
RUN chmod +x /start.sh /create-flag.sh

# Create msfadmin user with password 'msfadmin' for both telnet and SSH access
RUN useradd -m -s /bin/bash msfadmin && \
    echo 'msfadmin:msfadmin' | chpasswd && \
    usermod -aG sudo msfadmin

ENTRYPOINT ["/create-flag.sh"]
