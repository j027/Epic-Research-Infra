# Epic-Research-Infra
This repository is to store and track changes to the infrastructure being developed for the research project hosted by EPIC research at UMBC.

# Cybersecurity Lab Environment

This Docker environment provides a realistic cybersecurity lab setup for educational purposes, consisting of three machines in an isolated network environment.

## Architecture Overview

```
Network → Port 2222 → Kali Jump Box (172.20.<subnet>.10)
                            ↓ Internal Network
                       Ubuntu Target 1 (172.20.<subnet>.11)
                       Ubuntu Target 2 (172.20.<subnet>.12)
```

## Usage

> You need to install docker for this to work.

### Build and start up containers
```
sudo docker compose up -d --build
```

### Tear down and destroy containers
```
sudo docker compose down
```

> Credentials for all containers are student:student123