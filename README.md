# Epic Research Infrastructure

Infrastructure and automation for a multi‑host cybersecurity lab environment used by EPIC Research (UMBC). The system provisions isolated per‑student lab environments (jump box + targets) using Docker Compose and a simple CSV roster.

---

## 1. Overview

The lab environment simulates a corporate network per student with isolated environments for cybersecurity training. Each student gets their own isolated single-network environment with two containers (Kali jump box + Ubuntu target). SSH access is exposed via a unique high port on the host.

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
* Docker
* Docker Compose (plugin or standalone)
* Python 3 (>=3.10 recommended)
* Sufficient system resources (CPU, RAM, disk) for number of concurrent students

### 2.1 Install Git
Git is usually pre-installed on most Linux distributions, but ensure it's present:
```bash
sudo apt update
sudo apt install -y git
```

> **Note:** If using a different Linux distribution, use the appropriate package manager (e.g., `dnf`, `yum`, `pacman`, `zypper`).

### 2.2 Install Docker
Follow the official docs: https://docs.docker.com/engine/install/

For Ubuntu, a quick summary:
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
```
```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
 ```

### 2.3 Install Python 3 (if needed)
Python 3 is usually pre-installed on Ubuntu, but it doesn't hurt to ensure it's present:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

> **Note:** If using a different Linux distribution, use the appropriate package manager (e.g., `dnf`, `yum`, `pacman`, `zypper`).

> **Tip:** Use a virtual environment for development & testing (`python3 -m venv .venv`).

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

### 3.2 Assignment Logic (Summary)
* Ports: Allocate first free starting at 2222. All duplicates (including originals) are reallocated to guarantee uniqueness.
* Subnets: Deterministic hash → if occupied or duplicated, find next free.
* CSV is rewritten only if changes (new assignments) occur.

> After first `up` or `reconcile` run, distribute the updated CSV (or at least the port list) to students.

---

## 4. Initial Setup

### 4.1 Clone the Repository
First, clone this repository to your Linux host:
```bash
git clone https://github.com/j027/Epic-Research-Infra.git
cd Epic-Research-Infra
```

### 4.2 Copy Example Roster
```bash
cp students_example.csv students.csv
```
Populate `student_id` and `student_name` for each row. Leave `port` and `subnet_id` blank initially.

### 4.3 Build Images (first time ~5 min)
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

> After this stage, distribute the updated `students.csv` (or at least the port list) to students. This is needed for them to SSH in.
### 5.2 Reconcile Running State With CSV
```bash
./lab_manager.py class reconcile students.csv
```
* Adds missing student environments.
* Removes environments no longer present in the CSV.
* Fills in any missing assignments.

### 5.3 Stop & Remove All Student Environments (Destructive)
```bash
./lab_manager.py class down students.csv
```
> ⚠️ **Destructive:** Removes containers & ephemeral state. Any in‑container changes are lost.

### 5.4 Individual Student Lifecycle
| Action | Command | Effect |
| ------ | ------- | ------ |
| Recreate | `./lab_manager.py student recreate <student_id> students.csv` | ⚠️ Destroys & rebuilds that student's containers. |
| Status | `./lab_manager.py student status <student_id>` | Shows container states / ports. |
| Exec (interactive shell) | `./lab_manager.py student exec <student_id> --container kali` | Open a bash shell inside the specified container. |

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
> 🔐 **Require a password change**: Instruct students to run `passwd` on first login.

---

## 7. Security & Data Notes
* Isolation: Each student has their own isolated network; no cross‑student access (by design).
* Resource Limits: Each container has CPU (2 cores), memory (1GB), and PID limits (128 processes) to prevent resource exhaustion and fork bomb attacks.
* Ephemeral Changes: No host volumes are mounted. ALL changes inside containers are lost on `recreate` or class `down`.
* Do NOT manually edit assigned `port` / `subnet_id` values unless intentionally resolving a conflict. To clear an assignment, blank the field and run `reconcile`.
* Audit / inspection: Use `student status`, `student exec`, and `list` commands.
* Credentials: Instruct students to change the default password immediately.

---

## 8. Troubleshooting

| Issue | Check / Fix |
| ----- | ----------- |
| Student cannot SSH | Confirm port in CSV, ensure host firewall allows it, container running. |
| Duplicate ports reappear | Ensure only one authoritative CSV is edited; rerun `reconcile`. |
| Port already in use on host | Another service may occupy it; blank the `port` cell for that student (or pick a higher unused one) then run `reconcile`. |
| Wrong subnet allocation | Delete stale row assignments (ports/subnets) and rerun `up` / `reconcile`. |
| Containers not removed | Run `docker compose -p cyber-lab-<id> down -v --remove-orphans` manually. |
| Need clean slate | Stop everything, remove networks: `docker network prune` (⚠️ affects other networks—review first). |
| SSH host key changed | Image rebuild + container recreation generates new SSH keys (mainly during development). Remove old key: `ssh-keygen -R '[localhost]:2222'` (replace with actual host/port). |

### 8.1 SSH Host Key Changed Error
When containers are recreated **after the base image has been rebuilt**, new SSH host keys are generated. This typically happens during development when images are rebuilt, but is uncommon in normal operation. SSH clients will display a security warning:

```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
It is also possible that a host key has just been changed.
Host key verification failed.
```

**Fix:** Remove the old host key from your known_hosts file:
```bash
ssh-keygen -R '[localhost]:2222'
```
Replace `localhost:2222` with the actual host and port for the student's container.

### 8.2 Recreate a Single Student (Destructive)
```bash
./lab_manager.py student recreate <student_id> students.csv
```
> ⚠️ Removes that student's runtime changes.

### 8.3 Exec Into Containers
```bash
./lab_manager.py student exec <student_id> --container kali
```
Container types: `kali`, `ubuntu1`.

---

## 9. Development & Local Testing

### 9.1 Quick Compose Test
```bash
sudo docker compose build
sudo docker compose up -d
```
Kali default forwarded port (if using base config): `2222`.

### 9.2 Tear Down
```bash
sudo docker compose down
```

### 9.3 Run Automated Tests
```bash
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
pytest -v
deactivate
```
Or without activation:
```bash
.venv/bin/python -m pytest -v
```

#### 9.3.2 Capacity Testing (Optional)
An optional capacity testing tool is available to determine the maximum number of concurrent students your system can handle. This uses binary search to efficiently find the breaking point.

**WARNING:** This test can take 30+ minutes and will heavily stress your system. Only run on hardware that matches your production environment.

```bash
pytest tests/test_capacity.py -v -s -m capacity
```

**What it does:**
- Uses binary search to find maximum student capacity
- Requires 100% success rate (worst-case scenario)
- Treats timeouts as failures (our timeouts are already generous)
- Allows performance degradation as long as all students succeed
- Provides detailed report with recommendations

**When to use:**
- Before deploying to production to validate hardware
- After infrastructure changes to verify capacity
- When planning for class size increases
- To establish safe operating limits

### 9.4 Parallel vs Sequential Operations
Some operations (e.g. class up/down) can run in parallel. The tool will prompt for confirmation before parallel execution. If output interleaving is confusing or the host is resource‑constrained, re-run with sequential mode:
```bash
./lab_manager.py --sequential class up students.csv
```

Parallel mode speeds up large cohorts; sequential mode is simpler to read.

## 10. Command Reference (Cheat Sheet)
| Goal | Command |
| ---- | ------- |
| Build images | `./lab_manager.py build` |
| Start class | `./lab_manager.py class up students.csv` |
| Reconcile | `./lab_manager.py class reconcile students.csv` |
| Stop class (⚠️ destructive) | `./lab_manager.py class down students.csv` |
| Recreate student (⚠️) | `./lab_manager.py student recreate <id> students.csv` |
| Student status | `./lab_manager.py student status <id>` |
| Exec into Kali | `./lab_manager.py student exec <id> --container kali` |
| List all | `./lab_manager.py list` |

---

## 11. License

This project is licensed under the Unlicense (public domain). See the [`LICENSE`](LICENSE) file for details.

### Third-Party Components

This project includes third-party software components with different licenses:

- **ubuntu-target1/**: Contains a Docker implementation of Metasploitable3
  - Docker implementation by heywoodlh: MIT License
  - Metasploitable3 by Rapid7, Inc.: BSD-3-Clause License
  - See [`ubuntu-target1/LICENSE`](ubuntu-target1/LICENSE) for full license text

For complete third-party licensing information, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---