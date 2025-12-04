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
               Kali Jump Box        (10.<subnet>.1.10)
                     │
                     │
       ┌─────────────┴─────────────┐
       │  Internal Network         │
       │  (10.<subnet>.1.0/24)     │
       │                           │
       │      Ubuntu Target 1      │
       └──────(10.<subnet>.1.11)───┘
```

**Network Architecture:**
- **Internal Network** (`10.<subnet>.1.0/24`): Contains Kali Jump Box + Ubuntu Target 1
- Each student has their own isolated network preventing cross-student access

### 1.2 Key Concepts
| Concept | Description |
| ------- | ----------- |
| Student ID | Unique identifier from the CSV (e.g. `student001`) used in naming & hashing. |
| Assigned Port | Unique host SSH port (≥ 2222) mapped to the student's Kali container. |
| Subnet ID | Deterministic (collision‑avoiding) value 1–254 used for the internal network (`10.<subnet>.1.0/24`). |
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

### 3.2 Assignment Logic
* Ports: Allocate first free starting at 2222. All duplicates (including originals) are reallocated to guarantee uniqueness.
* Subnets: Deterministic hash → if occupied or duplicated, find next free.
* CSV is rewritten only if changes (new assignments) occur.

> After first `up` or `reconcile` run, distribute the updated CSV (or at least the port list) to students.

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

> **Note:** Lab manager commands use `sudo` for Docker operations. Enter your password when prompted.

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

After provisioning, check the updated `students.csv` for each assigned port.

SSH pattern:
```bash
ssh -p <assigned_port> student@<host_ip>
```
Default credentials:
```
username: student
password: student123
```
> 🔐 **Require students to change their password** with `passwd` on first login.

---

## 7. Security Notes

* **Isolation:** Each student has their own isolated network; no cross‑student access.
* **Resource Limits:** Each container has CPU (2 cores), memory (1GB), and PID limits (128 processes).
* **Ephemeral Changes:** No host volumes are mounted. ALL changes inside containers are lost on `recreate` or `down`.
* **Credentials:** Instruct students to change the default password immediately.

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
Container types: `kali`, `ubuntu1`.

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

## 10. Command Reference

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
