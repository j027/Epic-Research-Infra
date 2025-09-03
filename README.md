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

# For Classroom Use
## Requirements
- Docker
- Docker Compose
- Linux Host to run docker
- Python 3

## Configure Students
Copy the students_example.csv file to students.csv
```bash
cp students_example.csv students.csv
```
Edit the new `students.csv` file to configure the student accounts.

You must populate the student id and student name columns for each student.
All other columns will be populated automatically when the script is used.
> The file can be named anything you want, but the rest of this guide assumes it is named students.csv.

## Build initial docker images
This is needed to set up the container images that will then be deployed in the classroom.
```bash
./lab_manager.py build
```

## Create environment
```bash
./lab_manager.py class up students.csv
```
## Reconcile with CSV
This will add or remove students based on changes to the CSV file.
```bash
./lab_manager.py class reconcile students.csv
```

## Spin Down Environment
```bash
./lab_manager.py class down students.csv
```

## Troubleshooting
### Recreate Student Containers
If a student has issues with their environment, their containers can be recreated like so.
```bash
./lab_manager.py student recreate <student_id> students.csv
```

#### Drop into shell in student container
For advanced users, if you would like to fix the student's container manually, you can drop into the shell like so.
```bash
./lab_manager.py student exec <student_id> <kali|ubuntu1|ubuntu2>
```
> kali|ubuntu1|ubuntu2 means the specific container you want to access and it should be one of those that you put in the command

### Check status of class containers
This allows checking the status of all running student containers, grouped by student.
```bash
./lab_manager.py list
```

# For Development

### Build and start up containers
This sets up the environment for a test student, making it easier to develop.
```bash
sudo docker compose build
sudo docker compose up -d
```

> The Kali Linux jump box will be forwarded at port 2222 and it will have a subnet id of 0.

### Tear down and destroy containers
```bash
sudo docker compose down
```

> Credentials for all containers are student:student123