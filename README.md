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
```

### Machines:

1. **Kali Linux Jump Box** (172.20.0.10)
   - Externally accessible via SSH on port 2222
   - Contains penetration testing tools
   - Acts as the entry point to the internal network

2. **Ubuntu Target 1** (172.20.0.11)
   - Internal network only
   - Web server with intentional vulnerabilities
   - Multiple user accounts for privilege escalation practice

3. **Ubuntu Target 2** (172.20.0.12)
   - Internal network only
   - Development server with database
   - Contains sensitive files and configurations

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB of available RAM
- 10GB of free disk space

### Setup and Launch

1. **Clone/Navigate to the project directory:**
   ```bash
   cd /path/to/EPIC-Project
   ```

2. **Build and start the environment:**
   ```bash
   docker-compose up -d --build
   ```
   This will build all three custom images and start the containers.

3. **Verify all containers are running:**
   ```bash
   docker-compose ps
   ```

4. **Access the Kali Jump Box:**
   ```bash
   ssh student@localhost -p 2222
   # Password: cybersec123
   ```

### Default Credentials

#### Kali Jump Box (External Access)
- **SSH Port:** 2222 (mapped from container port 22)
- **Users:**
  - `student` / `cybersec123` (sudo access)
  - `root` / `rootpass123`

#### Ubuntu Target 1 (Internal Only)
- **IP:** 172.20.0.11
- **Services:** SSH (22), HTTP (80), FTP (21)
- **Users:**
  - `student` / `student123` (sudo access)
  - `admin` / `admin456` (sudo access)
  - `user1` / `password`
  - `root` / `toor`

#### Ubuntu Target 2 (Internal Only)
- **IP:** 172.20.0.12
- **Services:** SSH (22), HTTP (80), PostgreSQL (5432), Node.js (3000)
- **Users:**
  - `student` / `student456` (sudo access)
  - `developer` / `dev123` (sudo access)
  - `backup` / `backup789`
  - `root` / `ubuntu`

## Security Features & Fork Bomb Protection

Each container has built-in protections against resource exhaustion attacks:

- **Process limits:** Max 100-200 processes per user
- **File descriptor limits:** Max 1024-2048 open files
- **Memory limits:** 1-2GB per container
- **CPU limits:** 0.5-1.0 CPU cores per container
- **Student users:** Additional restrictions (50-100 processes max)

These limits prevent fork bombs and other resource exhaustion attacks from affecting the host system.

## Lab Exercises

### Basic Network Discovery
1. From Kali, scan the internal network:
   ```bash
   nmap -sn 172.20.0.0/24
   nmap -sS 172.20.0.11-12
   ```

### SSH Access to Targets
```bash
# From Kali Jump Box
ssh student@172.20.0.11    # Password: student123
ssh student@172.20.0.12    # Password: student456
```

### Web Services
- Ubuntu Target 1: `http://172.20.0.11` (vulnerable PHP page at `/vulnerable.php`)
- Ubuntu Target 2: `http://172.20.0.12` (development server)

### Database Access (Ubuntu Target 2)
```bash
# PostgreSQL database
psql -h 172.20.0.12 -U dbuser -d testdb
# Password: dbpass123
```

## Management Commands

### Start the environment:
```bash
docker-compose up -d
```

### Stop the environment:
```bash
docker-compose down
```

### View logs:
```bash
docker-compose logs [service-name]
```

### Rebuild after changes:
```bash
docker-compose down
docker-compose up -d --build
```

### Reset environment (removes all data):
```bash
docker-compose down -v
docker-compose up -d --build
```

### Access container shells directly (for debugging):
```bash
docker exec -it kali-jump-box /bin/bash
docker exec -it ubuntu-target1 /bin/bash
docker exec -it ubuntu-target2 /bin/bash
```

## Scaling for a Class

For multiple students, you can:

1. **Run multiple instances** with different port mappings:
   ```bash
   # Student 1
   docker-compose -p student1 up -d
   
   # Student 2 (modify ports in docker-compose.yml first)
   docker-compose -p student2 -f docker-compose-student2.yml up -d
   ```

2. **Use environment variables** to customize passwords and ports per student

3. **Deploy on separate VMs** or use container orchestration platforms

## Troubleshooting

### Can't connect to SSH:
- Verify containers are running: `docker-compose ps`
- Check port mapping: `docker port kali-jump-box`
- Verify firewall settings on host

### Containers keep restarting:
- Check logs: `docker-compose logs [service-name]`
- Verify sufficient system resources
- Check for port conflicts

### Performance issues:
- Increase memory/CPU limits in docker-compose.yml
- Reduce number of running containers
- Monitor host system resources

## Educational Notes

This environment is designed for:
- Network scanning and reconnaissance
- SSH brute forcing and lateral movement
- Web application security testing
- Privilege escalation exercises
- Digital forensics practice

**⚠️ Security Warning:** This environment contains intentional vulnerabilities and should only be used in isolated lab environments. Never expose these containers directly to the internet.

## Files and Flags

Each target contains hidden files and flags for discovery exercises:
- Look for configuration files with credentials
- Search for backup files and hidden directories
- Practice file system enumeration techniques
- Find flags in user directories and system files

## Customization

To modify the environment:
1. Edit the respective Dockerfile in each service directory
2. Modify docker-compose.yml for network or resource changes
3. Rebuild with `docker-compose up -d --build`

For production use, consider:
- Using secrets management instead of hardcoded passwords
- Implementing user isolation per student
- Adding monitoring and logging
- Setting up automated reset procedures
