# Epic Research Infrastructure

Infrastructure and automation for a multi‑host cybersecurity lab environment used by EPIC Research (UMBC). The system provisions isolated per‑student lab environments (jump box + targets) using Docker Compose and a simple CSV roster.

---

## 1. Overview

The lab environment simulates a small internal network per student. Each student gets their own isolated network and a trio of containers (Kali jump box + Ubuntu targets). SSH access is exposed via a unique high port on the host.

### 1.1 Architecture
```
External Network → Host: <assigned SSH port>
                       │
                       ▼
               Kali Jump Box   (172.20.<subnet>.10)
                     │
       ┌───────────┴─────────── Internal / Per-Student Network (172.20.<subnet>.0/24)
       │                       
Ubuntu Target 1 (172.20.<subnet>.11)
Ubuntu Target 2 (172.20.<subnet>.12)
```

### 1.2 Key Concepts
| Concept | Description |
| ------- | ----------- |
| Student ID | Unique identifier from the CSV (e.g. `student001`) used in naming & hashing. |
| Assigned Port | Unique host SSH port (≥ 2222) mapped to the student's Kali container. |
| Subnet ID | Deterministic (collision‑avoiding) value 1–254 used to derive `172.20.<subnet>.0/24`. |
| Project Name | Docker Compose project prefix: `cyber-lab-<student_id>`. |
| CSV | Single source of truth for roster + (after first run) assigned ports/subnets. |

---

## 2. Requirements

Install on a Linux host with Docker:
* Docker
* Docker Compose (plugin or standalone)
* Python 3 (>=3.10 recommended)
* Sufficient system resources (CPU, RAM, disk) for number of concurrent students

### 2.1 Install Docker
Follow the official docs: https://docs.docker.com/engine/install/

### 2.2 Install Python 3 (if needed)
```bash
sudo apt update
sudo apt install -y python3 python3-pip
```

> Tip: Use a virtual environment for development & testing (`python3 -m venv .venv`).

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

### 4.1 Copy Example Roster
```bash
cp students_example.csv students.csv
```
Populate `student_id` and `student_name` for each row. Leave `port` and `subnet_id` blank initially.

### 4.2 Build Images (first time ~10 min)
```bash
./lab_manager.py build
```

---

## 5. Core Operations

### 5.1 Start / Provision All Students
```bash
./lab_manager.py class up students.csv
```
Creates (or reuses) per‑student networks & containers. Assigns any missing ports/subnets.

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
* Isolation: Each student has their own network; no cross‑student lateral movement (by design).
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

### 8.1 Recreate a Single Student (Destructive)
```bash
./lab_manager.py student recreate <student_id> students.csv
```
> ⚠️ Removes that student's runtime changes.

### 8.2 Exec Into Containers
```bash
./lab_manager.py student exec <student_id> --container kali
```
Container types: `kali`, `ubuntu1`, `ubuntu2`.

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
Licensed under the terms of the project license. See the [`LICENSE`](LICENSE) file.

---