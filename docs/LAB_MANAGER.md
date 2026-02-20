# Lab Manager - Multi-Host Deployment

This guide is for **instructors/administrators** deploying the lab environment for multiple students on a shared server. If you're a student setting up the lab on your own machine, see the main [README](../README.md).

---

## 1. Overview

The Lab Manager provisions isolated per-student lab environments (jump box + targets) using Docker Compose and a simple CSV roster. Each student gets their own isolated network with two containers (Kali jump box + Ubuntu target). SSH access is exposed via a unique high port on the host.

### 1.1 Architecture
```
External Network → Host: <assigned SSH port>
                       │
                       ▼
               Kali Jump Box        (10.<subnet>.42.10)
                     │
                     │
       ┌─────────────┴─────────────┐
       │  Internal Network         │
       │  (10.<subnet>.42.0/24)    │
       │                           │
       │      Ubuntu Target 1      │
       │      (10.<subnet>.42.11)  │
       │                           │
       │      Ubuntu Target 2      │
       └──────(10.<subnet>.42.231)─┘
```

**Network Architecture:**
- **Internal Network** (`10.<subnet>.42.0/24`): Contains Kali Jump Box + Ubuntu Targets
- Each student has their own isolated network preventing cross-student access
- **Target 1** (`file-server`): Standard target at `.11`
- **Target 2** (`build-server`): Hidden target at `.231` (intended for discovery via scanning)

### 1.2 Key Concepts
| Concept | Description |
| ------- | ----------- |
| Student ID | Unique identifier from the CSV (e.g. `student001`) used in naming & hashing. |
| Assigned Port | Unique host SSH port (≥ 2222) mapped to the student's Kali container. |
| Subnet ID | Deterministic (collision‑avoiding) value 1–254 used for the internal network (`10.<subnet>.42.0/24`). |
| Project Name | Docker Compose project prefix: `cyber-lab-<student_id>`. |
| CSV | Single source of truth for roster + (after first run) assigned ports/subnets. |

---

## 2. Requirements

Install on a Linux host with Docker:
* Git
* Docker Engine
* Docker Compose (plugin or standalone)
* Python 3 (>=3.10 recommended)
* Sufficient system resources (CPU, RAM, disk) for number of concurrent students

### 2.1 Install Git
```bash
sudo apt update
sudo apt install -y git
```

### 2.2 Install Docker Engine
Follow the official docs: https://docs.docker.com/engine/install/

For Ubuntu:
```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.3 Install Python 3
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

---

## 3. CSV Roster

The CSV drives everything. Example (`students_example.csv`):

```csv
student_id,student_name,port,subnet_id
student001,Alice Smith,,
student002,Bob Jones,,
```

### 3.1 Columns
| Column | Required | Filled By | Notes |
| ------ | -------- | --------- | ----- |
| `student_id` | Yes | You | Stable unique token. Used for naming & hashing. |
| `student_name` | Yes | You | Display / reference only. |
| `port` | No (blank initially) | Tool | Auto‑assigned ≥ 2222. Regenerated only if duplicate/conflict. |
| `subnet_id` | No (blank initially) | Tool | Deterministic hash + collision avoidance (1–254). |
| `password` | No (blank initially) | Tool | Diceware‑style password (e.g. `bold-creek-jump-sage`), generated on first run. |

### 3.2 Assignment Logic
* Ports: Allocate first free starting at 2222. All duplicates (including originals) are reallocated to guarantee uniqueness.
* Subnets: Deterministic hash → if occupied or duplicated, find next free.
* Passwords: A diceware‑style password (4 random hyphen‑separated words from the [EFF large wordlist](https://www.eff.org/dice)) is generated for each student on first run. Easy to type, hard to guess. Passwords are stored in the CSV and persist across restarts.
* CSV is rewritten only if changes (new assignments) occur.

> After first `up` or `reconcile` run, distribute the updated CSV (or at minimum each student's port and password) to students. If you trust students not to connect to other students' containers, you may distribute the whole spreadsheet.

---

## 4. Initial Setup

### 4.1 Clone the Repository
```bash
git clone https://github.com/j027/Epic-Research-Infra.git
cd Epic-Research-Infra
```

### 4.2 Copy Example Roster
```bash
cp students_example.csv students.csv
```
Populate `student_id` and `student_name` for each row. Leave `port` and `subnet_id` blank initially.

### 4.3 Build Images
```bash
./lab_manager.py build
```

> **Note:** The lab manager auto‑detects whether `sudo` is needed for Docker operations. Override with `--sudo` or `--no-sudo` flags.

---

## 5. Core Operations

### 5.1 Start / Provision All Students
```bash
./lab_manager.py class up students.csv
```
Creates (or reuses) per‑student networks & containers. Assigns any missing ports/subnets.

> After this stage, distribute the updated `students.csv` (or at least the port list) to students.

### 5.2 Reconcile Running State With CSV
```bash
./lab_manager.py class reconcile students.csv
```
* Adds missing student environments.
* Removes environments no longer present in the CSV.
* Fills in any missing assignments.

### 5.3 Stop & Remove All Student Environments
```bash
./lab_manager.py class down students.csv
```
> ⚠️ **Destructive:** Removes containers & ephemeral state. Any in‑container changes are lost.
> However, this is safe to run between labs since there's no persistent data to save.

### 5.4 Individual Student Lifecycle
| Action | Command |
| ------ | ------- |
| Recreate | `./lab_manager.py student recreate <student_id> students.csv` |
| Status | `./lab_manager.py student status <student_id>` |
| Exec | `./lab_manager.py student exec <student_id> --container kali` |

### 5.5 List All Lab Containers
```bash
./lab_manager.py list
```

---

## 6. Student Access

After provisioning, check the updated `students.csv` for each assigned port and password.

SSH pattern:
```bash
ssh -p <assigned_port> student@<host_ip>
```

### 6.1 Password Behaviour

| Deployment Mode | Password | Source |
| --------------- | -------- | ------ |
| **Lab Manager** (multi‑student server) | Unique diceware‑style per student (e.g. `bold-creek-jump-sage`) | `password` column in CSV, set via `STUDENT_PASSWORD` env var at container start |
| **Standalone** (`docker compose up`) | `student123` | Default in Dockerfile (no env var set) |

When the Lab Manager provisions containers it passes a `STUDENT_PASSWORD` environment variable to the Kali jump box. The container's entrypoint script changes the `student` user's password at boot. If the variable is empty (standalone mode), the default `student123` password is kept.

### 6.2 Distributing Credentials

After running `class up` or `reconcile`, distribute credentials to students. Options:

1. **Per‑student extract** – give each student only their row (port + password).
2. **Whole CSV** – acceptable if you trust students not to connect to other students' containers.

### 6.3 Sudo Access

The `student` user has **passwordless sudo** (`NOPASSWD`) on the Kali jump box, so students never need to type the randomized password after logging in.

---

## 7. Security Notes

* **Isolation:** Each student has their own isolated network; no cross‑student access.
* **Resource Limits:** Each container has CPU (2 cores), memory (1GB), and PID limits (128 processes).
* **Ephemeral Changes:** No host volumes are mounted. ALL changes inside containers are lost on `recreate` or `down`.
* **Passwords:** Each student receives a unique diceware‑style password (e.g. `bold-creek-jump-sage`) generated by the lab manager. Passwords are easy to type and stored in the roster CSV. Students have passwordless sudo on the jump box for convenience.

---

## 8. Troubleshooting

| Issue | Fix |
| ----- | --- |
| Student cannot SSH | Confirm port in CSV, check firewall, verify container is running. |
| Duplicate ports | Ensure only one CSV is edited; rerun `reconcile`. |
| Port in use on host | Blank the `port` cell and run `reconcile`. |
| Containers not removed | Run `docker compose -p cyber-lab-<id> down -v --remove-orphans` manually. |
| SSH host key changed | `ssh-keygen -R '[<host>]:<port>'` |

### 8.1 Recreate a Single Student
```bash
./lab_manager.py student recreate <student_id> students.csv
```

### 8.2 Exec Into Containers
```bash
./lab_manager.py student exec <student_id> --container kali
```
Container types: `kali`, `ubuntu1`, `ubuntu2`.

---

## 9. Development & Testing

### 9.1 Run Automated Tests
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
pytest -v
```

### 9.2 Capacity Testing
```bash
pytest tests/test_capacity.py -v -s -m capacity
```

### 9.3 Parallel vs Sequential Operations
```bash
./lab_manager.py --sequential class up students.csv
```

---

## 10. Cleaning Up (Free Disk Space)

To reclaim disk space after decommissioning the lab:

### Remove All Student Environments
```bash
./lab_manager.py class down students.csv
```

### Remove Lab Images
```bash
sudo docker rmi epic-research-infra-kali-jump:latest epic-research-infra-ubuntu-target1:latest epic-research-infra-ubuntu-target2:latest
```

### Clear Build Cache
```bash
sudo docker builder prune
```

> 💡 Run `sudo docker system df` to see current disk usage.

---

## 11. Command Reference

| Goal | Command |
| ---- | ------- |
| Build images | `./lab_manager.py build` |
| Start class | `./lab_manager.py class up students.csv` |
| Reconcile | `./lab_manager.py class reconcile students.csv` |
| Stop class | `./lab_manager.py class down students.csv` |
| Recreate student | `./lab_manager.py student recreate <id> students.csv` |
| Student status | `./lab_manager.py student status <id>` |
| Exec into Kali | `./lab_manager.py student exec <id> --container kali` |
| List all | `./lab_manager.py list` |
