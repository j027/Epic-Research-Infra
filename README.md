# Epic Research Infrastructure

This repository stores and tracks changes to the infrastructure being developed for the research project hosted by EPIC research at UMBC.

## Overview

This Docker environment provides a realistic cybersecurity lab setup for educational purposes, consisting of three machines in an isolated network environment.

### Architecture

```
External Network → Port 2222 → Kali Jump Box (172.20.<subnet>.10)
                                       ↓ Internal Network
                                Ubuntu Target 1 (172.20.<subnet>.11)
                                Ubuntu Target 2 (172.20.<subnet>.12)
```

## Classroom Use

### Requirements

- Docker
- Docker Compose  
- Linux host to run Docker
- Python 3

### Initial Setup

#### 1. Configure Students

Copy the example students file to create your configuration:

```bash
cp students_example.csv students.csv
```

Edit the new `students.csv` file to configure the student accounts.

**Important:** You must populate the student ID and student name columns for each student. All other columns will be populated automatically when the script is used.

> **Note:** The file can be named anything you want, but the rest of this guide assumes it is named `students.csv`.

#### 2. Build Docker Images

Build the initial Docker images that will be deployed in the classroom:

```bash
./lab_manager.py build
```

### Lab Management

#### Start Lab Environment

```bash
./lab_manager.py class up students.csv
```

#### Reconcile with CSV

Add or remove students based on changes to the CSV file:

```bash
./lab_manager.py class reconcile students.csv
```

#### Stop Lab Environment

```bash
./lab_manager.py class down students.csv
```

### Access & credentials

Default login for lab containers:
- Username: `student`
- Password: `student123`

**Important:** Students must change their password immediately after first login using the `passwd` command.

### Troubleshooting

#### Recreate Student Containers

If a student has issues with their environment, their containers can be recreated:

```bash
./lab_manager.py student recreate <student_id> students.csv
```

#### Access Student Container Shell

For advanced users who need to manually fix a student's container:

```bash
./lab_manager.py student exec <student_id> <container_type>
```

**Container types:** `kali`, `ubuntu1`, or `ubuntu2`

#### Check Container Status

View the status of all running student containers, grouped by student:

```bash
./lab_manager.py list
```

## Development

### Quick Start

Set up the environment for a test student to make development easier:

```bash
sudo docker compose build
sudo docker compose up -d
```

> **Note:** The Kali Linux jump box will be forwarded at port 2222 and will have a subnet ID of 0.

### Cleanup

```bash
sudo docker compose down
```

### Running Tests

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-test.txt
pytest
deactivate
```