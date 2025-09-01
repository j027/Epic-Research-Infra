#!/usr/bin/env python3
"""
Cybersecurity Lab Environment Manager

This script manages Docker containers for a cybersecurity lab environment
using environment variables with the existing docker-compose.yml file.

Author: EPIC Research Lab
"""

import argparse
import csv
import subprocess
import os
import json
import hashlib
import re
from typing import List, Dict, Optional, Set, TypedDict
from concurrent.futures import ThreadPoolExecutor, as_completed


class StudentData(TypedDict):
    student_id: str
    student_name: str
    port: int
    subnet_id: Optional[int]


class LabManager:
    def __init__(self, compose_file: str = "docker-compose.yml", use_sudo: bool = True):
        """Initialize the Lab Manager with the docker-compose file path."""
        self.compose_file = compose_file
        self.use_sudo = use_sudo
        
    def run_command(self, command: List[str], env: Optional[Dict[str, str]] = None, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a shell command with optional environment variables."""
        try:
            # Copy command so we don't mutate caller list
            cmd = list(command)
            
            # Prepare merged env for non-inline use
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
            
            # If using sudo for docker, inline env vars with `sudo env VAR=val ...` so they are preserved
            run_env: Optional[Dict[str, str]] = full_env
            if self.use_sudo and cmd and cmd[0] == "docker":
                if env:
                    env_pairs = [f"{k}={v}" for k, v in env.items()]
                    cmd = ["sudo", "env"] + env_pairs + cmd
                    run_env = None  # env already passed inline to child via sudo env
                else:
                    cmd = ["sudo"] + cmd
            
            print(f"Running: {' '.join(cmd)}")
            if env and not (self.use_sudo and command and command[0] == "docker"):
                print(f"With env: {env}")
            
            result = subprocess.run(
                cmd, 
                capture_output=capture_output, 
                text=True, 
                check=True,
                env=run_env
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            raise
    
    def build_images(self) -> bool:
        """Build all Docker images defined in the compose file."""
        print("Building Docker images...")
        try:
            self.run_command(["docker", "compose", "build"], capture_output=False)
            print("✅ Images built successfully!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to build images")
            return False
    
    def get_used_subnets(self) -> Set[int]:
        """Get set of subnet IDs currently in use by lab containers."""
        try:
            result = self.run_command([
                "docker", "network", "ls", "--format", "json",
                "--filter", "name=cyber-lab-"
            ])
            
            used_subnets = set()
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        network = json.loads(line)
                        name = network.get('Name', '')
                        if name.startswith('cyber-lab-'):
                            # Get network details to extract subnet
                            try:
                                inspect_result = self.run_command([
                                    "docker", "network", "inspect", name
                                ])
                                network_details = json.loads(inspect_result.stdout)
                                if network_details and len(network_details) > 0:
                                    ipam = network_details[0].get('IPAM', {})
                                    config = ipam.get('Config', [])
                                    if config and len(config) > 0:
                                        subnet = config[0].get('Subnet', '')
                                        # Extract subnet ID from format 172.20.X.0/24
                                        if subnet.startswith('172.20.') and subnet.endswith('.0/24'):
                                            subnet_id = int(subnet.split('.')[2])
                                            used_subnets.add(subnet_id)
                            except (subprocess.CalledProcessError, ValueError, KeyError, IndexError):
                                pass
            
            return used_subnets
        except subprocess.CalledProcessError:
            return set()
    
    def calculate_subnet_id(self, student_id: str, used_subnets: Set[int]) -> int:
        """Calculate subnet ID from student ID hash with collision avoidance."""
        # Hash the student ID and convert to integer
        hash_obj = hashlib.md5(student_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Map to valid subnet range (1-254, avoiding 0 and 255)
        base_subnet = (hash_int % 254) + 1
        
        # Check for collisions and find nearest available
        subnet_id = base_subnet
        while subnet_id in used_subnets:
            subnet_id = (subnet_id % 254) + 1  # Wrap around if needed
            # If we've checked all possibilities, just use the original
            if subnet_id == base_subnet:
                break
        
        return subnet_id
    
    def get_student_env(self, student_id: str, student_name: str, port: int, subnet_id: Optional[int] = None) -> Dict[str, str]:
        """Generate environment variables for a specific student."""
        # Use provided subnet_id if available, otherwise calculate from student ID
        if subnet_id is None:
            # Get currently used subnets to avoid collisions
            used_subnets = self.get_used_subnets()
            subnet_id = self.calculate_subnet_id(student_id, used_subnets)
        
        return {
            'STUDENT_ID': student_id,
            'STUDENT_NAME': student_name,
            'SSH_PORT': str(port),
            'SUBNET_ID': str(subnet_id),
            'NETWORK_NAME': f'cyber-lab-{student_id}'
        }
    
    def get_used_ports(self) -> Set[int]:
        """Get set of ports currently in use by lab containers."""
        try:
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json",
                "--filter", "name=cyber-lab-"
            ])
            
            used_ports = set()
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        ports = container.get('Ports', '')
                        
                        # Extract port mappings from the Ports field
                        # Format like: "0.0.0.0:2222->22/tcp, [::]:2222->22/tcp"
                        if ports:
                            import re
                            # Find all port mappings in format "host_port->container_port"
                            port_matches = re.findall(r'(\d+)->\d+', ports)
                            for port_str in port_matches:
                                port = int(port_str)
                                if port >= 2222:  # Only consider our SSH ports
                                    used_ports.add(port)
            
            return used_ports
        except (subprocess.CalledProcessError, ValueError):
            return set()
    
    def auto_assign_port(self, existing_ports: Set[int]) -> int:
        """Auto-assign a unique port starting from 2222."""
        used_ports = self.get_used_ports()
        used_ports.update(existing_ports)
        
        # Start from 2222 and find first available port
        port = 2222
        while port in used_ports:
            port += 1
        
        return port
    
    def write_students_csv(self, csv_file: str, students: List[StudentData]) -> bool:
        """Write student data back to CSV file with updated ports and subnet IDs."""
        try:
            # Read the original file to preserve column order and any extra columns
            fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
            
            # Check if file exists to see what columns it originally had
            existing_columns: List[str] = []
            try:
                with open(csv_file, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    existing_columns = list(reader.fieldnames or [])
            except FileNotFoundError:
                pass
            
            # Preserve original column order and add new ones if needed
            if existing_columns:
                # Keep original columns and add missing ones
                for col in ['port', 'subnet_id']:
                    if col not in existing_columns:
                        existing_columns.append(col)
                fieldnames = existing_columns
            
            # Write updated data
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for student in students:
                    # Calculate subnet ID for this student
                    subnet_id = self.calculate_subnet_id(student['student_id'], set())
                    
                    row = {
                        'student_id': student['student_id'],
                        'student_name': student['student_name'],
                        'port': student['port'],
                        'subnet_id': subnet_id
                    }
                    
                    # Add any extra columns that might exist
                    for col in fieldnames:
                        if col not in row:
                            row[col] = ''
                    
                    writer.writerow(row)
            
            print(f"✅ Updated CSV file {csv_file} with current port and subnet assignments")
            return True
            
        except Exception as e:
            print(f"❌ Failed to write CSV file: {e}")
            return False
    
    def read_students_csv(self, csv_file: str, update_if_changed: bool = True) -> List[StudentData]:
        """Read student data from CSV file."""
        students: List[StudentData] = []
        assigned_ports: Set[int] = set()
        changes_made = False
        
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Expected columns: student_id, student_name, port (port is optional)
                    student_id = row['student_id'].strip()
                    student_name = row['student_name'].strip()
                    
                    # Handle port assignment - more robust checking
                    port_value = ''
                    if 'port' in row and row['port'] is not None:
                        port_value = str(row['port']).strip()
                    
                    if port_value and port_value.isdigit() and int(port_value) > 0:
                        # Port is provided and valid
                        port = int(port_value)
                    else:
                        # No port provided, empty, or invalid port - auto-assign
                        port = self.auto_assign_port(assigned_ports)
                        print(f"🔧 Auto-assigned port {port} to student {student_id}")
                        changes_made = True
                    
                    # Check for port conflicts with already assigned ports in this CSV
                    if port in assigned_ports:
                        print(f"⚠️  Port conflict detected for {student_id}, auto-assigning new port")
                        port = self.auto_assign_port(assigned_ports)
                        print(f"🔧 Auto-assigned port {port} to student {student_id}")
                        changes_made = True
                    
                    # Handle subnet_id - more robust checking
                    subnet_value = ''
                    if 'subnet_id' in row and row['subnet_id'] is not None:
                        subnet_value = str(row['subnet_id']).strip()
                    
                    subnet_id = None
                    if subnet_value and subnet_value.isdigit() and int(subnet_value) > 0:
                        subnet_id = int(subnet_value)
                    else:
                        # No subnet_id provided, empty, or invalid - calculate it and mark for update
                        used_subnets = self.get_used_subnets()
                        subnet_id = self.calculate_subnet_id(student_id, used_subnets)
                        changes_made = True
                    
                    assigned_ports.add(port)
                    
                    students.append({
                        'student_id': student_id,
                        'student_name': student_name,
                        'port': port,
                        'subnet_id': subnet_id
                    })
                    
            print(f"✅ Loaded {len(students)} students from {csv_file}")
            
            # Write back to CSV if we made changes and update is requested
            if changes_made and update_if_changed:
                self.write_students_csv(csv_file, students)
            
            return students
        except FileNotFoundError:
            print(f"❌ CSV file {csv_file} not found")
            return []
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return []
    
    def spin_up_student(self, student_id: str, student_name: str, port: int, subnet_id: Optional[int] = None) -> bool:
        """Spin up containers for a specific student."""
        print(f"🚀 Spinning up containers for student: {student_name} ({student_id}) on port {port}")
        
        env = self.get_student_env(student_id, student_name, port, subnet_id)
        
        try:
            # Use project name to isolate each student's containers
            self.run_command([
                "docker", "compose", 
                "-f", self.compose_file,
                "-p", f"cyber-lab-{student_id}",  # Project name for isolation
                "up", "-d"
            ], env=env, capture_output=False)
            print(f"✅ Containers started for {student_name}")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to start containers for {student_name}")
            return False
    
    def spin_down_student(self, student_id: str) -> bool:
        """Spin down containers for a specific student."""
        print(f"🛑 Spinning down containers for student: {student_id}")
        
        try:
            # Get the student's environment to ensure we use the same network name
            # We need minimal env to make sure compose finds the right network
            env = {
                'STUDENT_ID': student_id,
                'NETWORK_NAME': f'cyber-lab-{student_id}'
            }
            
            # Use project name to target specific student's containers
            self.run_command([
                "docker", "compose",
                "-f", self.compose_file,
                "-p", f"cyber-lab-{student_id}",  # Project name for isolation
                "down", "--remove-orphans"
            ], env=env, capture_output=False)
            
            print(f"✅ Containers removed for student {student_id}")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to remove containers for student {student_id}")
            return False
    
    def spin_up_class(self, csv_file: str, parallel: bool = True) -> bool:
        """Spin up containers for all students in the CSV file."""
        students = self.read_students_csv(csv_file)
        if not students:
            return False
        
        print(f"🚀 Spinning up containers for {len(students)} students...")
        
        if parallel:
            # Parallel execution
            success_count = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                future_to_student = {
                    executor.submit(
                        self.spin_up_student, 
                        student['student_id'], 
                        student['student_name'], 
                        student['port'],
                        student['subnet_id']
                    ): student for student in students
                }
                
                # Collect results
                for future in as_completed(future_to_student):
                    student = future_to_student[future]
                    try:
                        if future.result():
                            success_count += 1
                    except Exception as exc:
                        print(f"❌ Student {student['student_id']} generated an exception: {exc}")
        else:
            # Sequential execution
            success_count = 0
            for student in students:
                if self.spin_up_student(
                    student['student_id'], 
                    student['student_name'], 
                    student['port'],
                    student['subnet_id']
                ):
                    success_count += 1
        
        print(f"✅ Successfully started containers for {success_count}/{len(students)} students")
        return success_count == len(students)
    
    def spin_down_class(self, csv_file: str, parallel: bool = True) -> bool:
        """Spin down containers for all students in the CSV file."""
        students = self.read_students_csv(csv_file)
        if not students:
            return False
        
        print(f"🛑 Spinning down containers for {len(students)} students...")
        
        if parallel:
            # Parallel execution
            success_count = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                future_to_student = {
                    executor.submit(self.spin_down_student, student['student_id']): student 
                    for student in students
                }
                
                # Collect results
                for future in as_completed(future_to_student):
                    student = future_to_student[future]
                    try:
                        if future.result():
                            success_count += 1
                    except Exception as exc:
                        print(f"❌ Student {student['student_id']} generated an exception: {exc}")
        else:
            # Sequential execution
            success_count = 0
            for student in students:
                if self.spin_down_student(student['student_id']):
                    success_count += 1
        
        print(f"✅ Successfully removed containers for {success_count}/{len(students)} students")
        return success_count == len(students)
    
    def get_running_students(self) -> Set[str]:
        """Get set of student IDs that currently have running containers."""
        try:
            # Look for containers with our project naming pattern
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json",
                "--filter", "name=cyber-lab-"
            ])
            
            student_ids = set()
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        names = container.get('Names', '')
                        
                        # Extract student ID from container names
                        # Names like: cyber-lab-student001-kali-jump-1
                        if names:
                            for name in names.split(','):
                                if 'cyber-lab-' in name:
                                    # Extract student ID from project prefix
                                    parts = name.split('-')
                                    if len(parts) >= 3 and parts[0] == 'cyber' and parts[1] == 'lab':
                                        student_id = parts[2]
                                        student_ids.add(student_id)
                                        break
            
            return student_ids
        except subprocess.CalledProcessError:
            print("❌ Failed to get running students")
            return set()
    
    def reconcile_with_csv(self, csv_file: str) -> bool:
        """Reconcile current Docker state with CSV file."""
        students = self.read_students_csv(csv_file)
        if not students:
            return False
        
        # Get expected student IDs from CSV
        expected_students = {s['student_id']: s for s in students}
        expected_ids = set(expected_students.keys())
        
        # Get current running student IDs
        running_ids = self.get_running_students()
        
        # Find students to add and remove
        to_add = expected_ids - running_ids
        to_remove = running_ids - expected_ids
        
        print(f"\n🔄 Reconciling lab environment:")
        print(f"Expected students: {len(expected_ids)}")
        print(f"Currently running: {len(running_ids)}")
        print(f"To add: {len(to_add)}")
        print(f"To remove: {len(to_remove)}")
        
        success = True
        
        # Remove extra students
        if to_remove:
            print(f"\n🛑 Removing {len(to_remove)} extra students...")
            for student_id in to_remove:
                if not self.spin_down_student(student_id):
                    success = False
        
        # Add missing students
        if to_add:
            print(f"\n🚀 Adding {len(to_add)} missing students...")
            for student_id in to_add:
                student_data = expected_students[student_id]
                if not self.spin_up_student(
                    student_data['student_id'],
                    student_data['student_name'],
                    student_data['port'],
                    student_data['subnet_id']
                ):
                    success = False
        
        if not to_add and not to_remove:
            print("✅ Environment already matches CSV file - no changes needed")
        elif success:
            print("✅ Reconciliation completed successfully")
        else:
            print("❌ Reconciliation completed with some errors")
        
        return success
    
    def spin_up_single_student(self, student_id: str, csv_file: str) -> bool:
        """Spin up containers for a single student from CSV file."""
        students = self.read_students_csv(csv_file)
        student_data = next((s for s in students if s['student_id'] == student_id), None)
        
        if not student_data:
            print(f"❌ Student {student_id} not found in CSV file")
            return False
        
        return self.spin_up_student(
            student_data['student_id'],
            student_data['student_name'],
            student_data['port'],
            student_data['subnet_id']
        )
    
    def recreate_student(self, student_id: str, csv_file: str) -> bool:
        students = self.read_students_csv(csv_file)
        student_data = next((s for s in students if s['student_id'] == student_id), None)
        
        if not student_data:
            print(f"❌ Student {student_id} not found in CSV file")
            return False
        
        print(f"🔄 Recreating containers for student: {student_data['student_name']} ({student_id})")
        
        # First spin down
        self.spin_down_student(student_id)
        
        # Then spin up
        return self.spin_up_student(
            student_data['student_id'],
            student_data['student_name'],
            student_data['port'],
            student_data['subnet_id']
        )
    
    def list_student_containers(self, student_id: str) -> List[Dict[str, str]]:
        """List all containers for a specific student."""
        try:
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json",
                "--filter", f"name=cyber-lab-{student_id}-"
            ])
            
            containers: List[Dict[str, str]] = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    containers.append(json.loads(line))
            
            return containers
        except subprocess.CalledProcessError:
            print(f"❌ Failed to list containers for student {student_id}")
            return []
    
    def show_student_status(self, student_id: str) -> None:
        """Show detailed status for a student's containers."""
        containers = self.list_student_containers(student_id)
        
        if not containers:
            print(f"No containers found for student {student_id}")
            return
        
        print(f"\n📋 Containers for student {student_id}:")
        print("-" * 80)
        
        for container in containers:
            name = container.get('Names', 'Unknown')
            status = container.get('State', 'Unknown')
            ports = container.get('Ports', 'None')
            
            print(f"Container: {name}")
            print(f"  Status: {status}")
            print(f"  Ports: {ports}")
            print()
    
    def show_all_students(self) -> None:
        """Show all lab containers grouped by student."""
        try:
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json",
                "--filter", "name=cyber-lab-"
            ])
            
            if not result.stdout.strip():
                print("No lab containers found")
                return
            
            # Group containers by student ID
            students = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    container = json.loads(line)
                    names = container.get('Names', '')
                    
                    # Extract student ID from container names
                    student_id = None
                    if names:
                        for name in names.split(','):
                            if 'cyber-lab-' in name:
                                # Extract student ID from project prefix
                                parts = name.split('-')
                                if len(parts) >= 3 and parts[0] == 'cyber' and parts[1] == 'lab':
                                    student_id = parts[2]
                                    break
                    
                    if student_id:
                        if student_id not in students:
                            students[student_id] = []
                        students[student_id].append(container)
            
            print("\n📋 All Lab Containers:")
            print("=" * 80)
            
            for student_id, containers in students.items():
                print(f"\nStudent: {student_id}")
                print("-" * 40)
                for container in containers:
                    names = container.get('Names', 'Unknown')
                    status = container.get('State', 'Unknown')
                    ports = container.get('Ports', 'None')
                    print(f"  {names} - {status} - {ports}")
        
        except subprocess.CalledProcessError:
            print("❌ Failed to list containers")
    
    def exec_into_container(self, student_id: str, container_type: str = "kali") -> None:
        """Execute into a student's container for investigation."""
        # Map container types to compose service names
        service_map = {
            "kali": "kali-jump",
            "ubuntu1": "ubuntu-target1", 
            "ubuntu2": "ubuntu-target2"
        }
        
        if container_type not in service_map:
            print(f"❌ Invalid container type: {container_type}")
            print("Valid types: kali, ubuntu1, ubuntu2")
            return
        
        # With docker-compose project naming, containers are named: cyber-lab-{student_id}-{service}-1
        container_name = f"cyber-lab-{student_id}-{service_map[container_type]}-1"
        
        print(f"🔍 Executing into {container_name}...")
        try:
            # Build command with sudo if needed
            cmd = ["docker", "exec", "-it", container_name, "/bin/bash"]
            if self.use_sudo:
                cmd = ["sudo"] + cmd
            
            # Use subprocess with no capture to allow interactive session
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            print(f"❌ Failed to execute into {container_name}")
            print("Make sure the container is running and the name is correct")
            # Try to list available containers for this student
            containers = self.list_student_containers(student_id)
            if containers:
                print(f"Available containers for {student_id}:")
                for container in containers:
                    print(f"  - {container.get('Names', 'Unknown')}")


def main():
    parser = argparse.ArgumentParser(description="Cybersecurity Lab Environment Manager")
    parser.add_argument("--compose-file", default="docker-compose.yml", 
                       help="Path to docker-compose file")
    parser.add_argument("--sequential", action="store_true",
                       help="Run operations sequentially instead of in parallel")
    parser.add_argument("--no-sudo", action="store_true",
                       help="Don't use sudo for docker commands (if running as root)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build Docker images")
    
    # Class management
    class_parser = subparsers.add_parser("class", help="Manage entire class")
    class_subparsers = class_parser.add_subparsers(dest="class_action")
    
    up_parser = class_subparsers.add_parser("up", help="Spin up class")
    up_parser.add_argument("csv_file", help="CSV file with student data")
    
    down_parser = class_subparsers.add_parser("down", help="Spin down class")
    down_parser.add_argument("csv_file", help="CSV file with student data")
    
    reconcile_parser = class_subparsers.add_parser("reconcile", help="Reconcile current state with CSV")
    reconcile_parser.add_argument("csv_file", help="CSV file with student data")
    
    # Student management
    student_parser = subparsers.add_parser("student", help="Manage individual student")
    student_subparsers = student_parser.add_subparsers(dest="student_action")
    
    add_parser = student_subparsers.add_parser("add", help="Add/start a single student")
    add_parser.add_argument("student_id", help="Student ID")
    add_parser.add_argument("csv_file", help="CSV file with student data")
    
    remove_parser = student_subparsers.add_parser("remove", help="Remove/stop a single student")
    remove_parser.add_argument("student_id", help="Student ID")
    
    recreate_parser = student_subparsers.add_parser("recreate", help="Recreate student containers")
    recreate_parser.add_argument("student_id", help="Student ID")
    recreate_parser.add_argument("csv_file", help="CSV file with student data")
    
    status_parser = student_subparsers.add_parser("status", help="Show student container status")
    status_parser.add_argument("student_id", help="Student ID")
    
    exec_parser = student_subparsers.add_parser("exec", help="Execute into student container")
    exec_parser.add_argument("student_id", help="Student ID")
    exec_parser.add_argument("--container", choices=["kali", "ubuntu1", "ubuntu2"], 
                           default="kali", help="Container type to execute into")
    
    # List all containers
    list_parser = subparsers.add_parser("list", help="List all lab containers")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Check if we need sudo
    use_sudo = not args.no_sudo
    lab_manager = LabManager(args.compose_file, use_sudo)
    parallel = not args.sequential
    
    if args.command == "build":
        lab_manager.build_images()
    
    elif args.command == "class":
        if args.class_action == "up":
            lab_manager.spin_up_class(args.csv_file, parallel)
        elif args.class_action == "down":
            lab_manager.spin_down_class(args.csv_file, parallel)
        elif args.class_action == "reconcile":
            lab_manager.reconcile_with_csv(args.csv_file)
        else:
            class_parser.print_help()
    
    elif args.command == "student":
        if args.student_action == "add":
            lab_manager.spin_up_single_student(args.student_id, args.csv_file)
        elif args.student_action == "remove":
            lab_manager.spin_down_student(args.student_id)
        elif args.student_action == "recreate":
            lab_manager.recreate_student(args.student_id, args.csv_file)
        elif args.student_action == "status":
            lab_manager.show_student_status(args.student_id)
        elif args.student_action == "exec":
            lab_manager.exec_into_container(args.student_id, args.container)
        else:
            student_parser.print_help()
    
    elif args.command == "list":
        lab_manager.show_all_students()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
