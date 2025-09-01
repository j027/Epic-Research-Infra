# Epic-Research-Infra
This repository is to store and track changes to the infrastructure being developed for the research project hosted by EPIC research at UMBC.

# Cybersecurity Lab Environment

This Docker environment provides a realistic cybersecurity lab setup for educational purposes, consisting of three machines in an isolated network environment.

## Architecture Overview

```
Internet → Port 2222 → Kali Jump Box (172.20.0.10)
                            ↓ Internal Network
                       Ubuntu Target 1 (172.20.0.11)
                       Ubuntu Target 2 (172.20.0.12)