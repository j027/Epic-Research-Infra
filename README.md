# Cybersecurity Lab Environment

A Docker-based cybersecurity training lab with a Kali Linux jump box and vulnerable Ubuntu targets. Run it locally on your own machine for hands-on practice.

---

## Quick Start
> If viewing this on GitHub, scroll down to read the full README before starting.

1. Install [Git](#1-install-git) and [Docker Desktop](#2-install-docker-desktop)
2. Clone and start the lab:
   ```bash
   git clone https://github.com/j027/Epic-Research-Infra.git
   cd Epic-Research-Infra
   docker compose build
   docker compose up -d
   ```
3. Connect to the Kali jump box:
   ```bash
   ssh student@127.0.0.1 -p 2222
   ```
   Password: `student123`

---

## Requirements

- **Git** – to clone this repository
- **Docker Desktop** – runs the lab containers

---

## 1. Install Git

### macOS
Git comes pre-installed. Verify with:
```bash
git --version
```
If not installed, you'll be prompted to install Xcode Command Line Tools automatically.

### Windows
Download and install from: https://git-scm.com/install/windows

Use default options during installation.

### Linux
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y git

# Fedora
sudo dnf install -y git

# Arch
sudo pacman -S git
```

---

## 2. Install Docker Desktop

Download and install Docker Desktop for your OS:

| OS | Download |
|----|----------|
| **macOS** | https://docs.docker.com/desktop/install/mac-install/ |
| **Windows** | https://docs.docker.com/desktop/install/windows-install/ |
| **Linux** | https://docs.docker.com/desktop/install/linux-install/ |

After installation:
1. Launch Docker Desktop
2. Wait for it to finish starting (whale icon stops animating)
3. Verify it works:
   ```bash
   docker --version
   ```

> **Windows Users:** If prompted, enable WSL 2 during installation. You may need to restart.

> **Linux Users:** You can also use [Docker Engine](https://docs.docker.com/engine/install/) instead of Docker Desktop.

---

## 3. Clone and Build

Open a terminal and run:

```bash
git clone https://github.com/j027/Epic-Research-Infra.git
cd Epic-Research-Infra
```

Build the lab images (first time takes ~5 minutes):
```bash
docker compose build
```

---

## 4. Running the Lab

### Start the Lab
```bash
docker compose up -d
```
This starts both containers in the background.

> This environment is reused across multiple labs; you do not need to reinstall it unless instructed.

### Shut Down the Lab (Full Reset)
```bash
docker compose down
```
Removes containers completely. All changes inside are lost—this gives you a fresh start next time.

> 💡 This is fine between labs since there's no persistent data to save.

---

## 5. Connecting to the Lab

SSH into the Kali jump box:
```bash
ssh student@127.0.0.1 -p 2222
```

**Credentials:**
- Username: `student`
- Password: `student123`

When you log in, you'll see network information including target IP addresses:

```
==========================================
  CYBERSECURITY LAB ENVIRONMENT
==========================================

Network Information:
  Internal Network: 10.0.1.0/24 (Gateway: 10.0.1.1)

Accessible Targets:
  Kali Jump Box:   kali-jump      (10.0.1.10)
  File Server:     file-server    (10.0.1.11)
  ???              ???            (Scan to find me!)
```

### Accessing Targets

From the Kali jump box, you can reach targets by **hostname** or **IP**:

```bash
# Using hostname (easier to remember)
ping file-server
nmap file-server

ping kali-jump
nmap kali-jump

# Using IP address
# file-server
ping 10.0.1.11
nmap 10.0.1.11

# kali-jump
ping 10.0.1.10
nmap 10.0.1.10
```

> 💡 **Tip:** Hostnames usually work and are easier to type than IP addresses.

---

## 6. Lab Architecture

```
Your Computer
     │
     │ SSH (port 2222)
     ▼
┌─────────────────────────────────────┐
│  Kali Jump Box (10.0.1.10)          │
│  - Your attack platform             │
│  - nmap, metasploit, john, etc.     │
└──────────────┬──────────────────────┘
               │
    Internal Network (10.0.1.0/24)
               │
┌──────────────┴──────────────────────┐
│  File Server (10.0.1.11)            │
│  - Vulnerable services              │
│  - Your practice target             │
│                                     │
│  [?] Hidden Target                  │
│  - Scan the network to find it!     │
└─────────────────────────────────────┘
```

---

## 7. Troubleshooting

### Port 2222 Already in Use
If you see an error about port 2222, another service is using it. Either stop that service or edit `docker-compose.yml` to use a different port (e.g., change `2222:22` to `2223:22`).

### SSH Host Key Changed
If you see a "REMOTE HOST IDENTIFICATION HAS CHANGED" warning after rebuilding:
```bash
ssh-keygen -R '[127.0.0.1]:2222'
```
Then try connecting again.

### Containers Not Starting
Make sure Docker Desktop is running (check for the whale icon in your system tray/menu bar).

### Check Container Status
```bash
docker compose ps
```

### View Container Logs
```bash
docker compose logs
```

---

## 8. Cleaning Up (Free Disk Space)

The lab images take up several gigabytes. When you're done with the labs that use this environment, you can reclaim disk space:

### Remove Lab Containers and Images
```bash
# Stop and remove containers
docker compose down

# Remove the lab images
docker rmi epic-research-infra-kali-jump:latest epic-research-infra-ubuntu-target1:latest epic-research-infra-ubuntu-target2:latest
```

### Clear Build Cache
Docker caches intermediate build layers. To free this space:
```bash
# Remove only build cache (safe - doesn't affect running containers)
docker builder prune
```

> 💡 **Tip:** Run `docker system df` to see how much space Docker is using.

> ⚠️ **Warning:** Avoid `docker system prune` unless you understand it—this removes ALL unused containers, networks, and images across your entire Docker installation, not just this lab.

---

## 9. Password Security

Since the lab runs locally on your own machine, the default password is fine—only you can access it.

If you want to change it anyway, use the command
```bash
passwd
```
after logging into the Kali jump box.

---

## 10. Multi-Host Deployment (Instructors)

For deploying the lab environment for an entire class on a shared server, see the [Lab Manager Guide](docs/LAB_MANAGER.md).

---

## 11. License

This project is licensed under the Unlicense (public domain). See [`LICENSE`](LICENSE) for details.

### Third-Party Components

- **ubuntu-target1/**: Docker implementation of Metasploitable3
  - Docker implementation by heywoodlh: MIT License
  - Metasploitable3 by Rapid7: BSD-3-Clause License
  - See [`ubuntu-target1/LICENSE`](ubuntu-target1/LICENSE) for details

For complete licensing information, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).