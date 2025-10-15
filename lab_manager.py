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
import time
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
    
    def _confirm_parallel_execution(self, operation_name: str) -> bool:
        """Helper function to confirm parallel execution with user."""
        print(f"\n⚠️  PARALLEL EXECUTION MODE")
        print(f"   Docker containers will be {operation_name} simultaneously.")
        print("   Your screen may show interleaved output from multiple operations.")
        print("   This is normal and expected behavior.")
        response = input("\n   Continue with parallel execution? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("   Switching to sequential execution...")
            return False
        return True
        
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
    
    def get_used_subnets(self, csv_file: str) -> Set[int]:
        """Get set of subnet IDs currently in use, using CSV as the only source of truth."""
        used_subnets = set()
        
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'subnet_id' in row and row['subnet_id']:
                        subnet_value = str(row['subnet_id']).strip()
                        if subnet_value and subnet_value.isdigit():
                            used_subnets.add(int(subnet_value))
            return used_subnets
        except FileNotFoundError:
            print(f"❌ CSV file {csv_file} not found")
            return set()
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
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
    
    def get_student_env(self, student_id: str, student_name: str, port: int, subnet_id: Optional[int] = None, csv_file: str = "students.csv") -> Dict[str, str]:
        """Generate environment variables for a specific student."""
        # Use provided subnet_id if available, otherwise calculate from student ID
        if subnet_id is None:
            # Get currently used subnets to avoid collisions, using CSV as source of truth
            used_subnets = self.get_used_subnets(csv_file)
            subnet_id = self.calculate_subnet_id(student_id, used_subnets)
        
        return {
            'STUDENT_ID': student_id,
            'STUDENT_NAME': student_name,
            'SSH_PORT': str(port),
            'SUBNET_ID': str(subnet_id),
            'NETWORK_NAME': f'cyber-lab-{student_id}'
        }
    
    def get_used_ports(self, csv_file: str) -> Set[int]:
        """Get set of ports currently in use, using CSV as the only source of truth."""
        used_ports = set()
        
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'port' in row and row['port']:
                        port_value = str(row['port']).strip()
                        if port_value and port_value.isdigit():
                            port = int(port_value)
                            if port >= 2222:  # Only consider our SSH ports
                                used_ports.add(port)
            return used_ports
        except FileNotFoundError:
            print(f"❌ CSV file {csv_file} not found")
            return set()
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return set()
    
    def auto_assign_port(self, existing_ports: Set[int], csv_file: str = "students.csv") -> int:
        """Auto-assign a unique port starting from 2222."""        
        # Start from 2222 and find first available port
        port = 2222
        while port in existing_ports:
            port += 1
        
        return port
    
    def ensure_assignments(self, students: List[StudentData], csv_file: str) -> List[StudentData]:
        """Ensure all students have valid port and subnet assignments. 
        This is the centralized assignment service that handles all assignment logic.
        Should never be called in parallel - CSV write is the critical section.
        """
        if not students:
            return students
        
        # Read current state from CSV to get baseline
        used_ports = self.get_used_ports(csv_file)
        used_subnets = self.get_used_subnets(csv_file)
        
        # Read existing student assignments to check ownership
        existing_students = self.read_students_csv(csv_file, update_if_changed=False)
        existing_port_owners = {}  # port -> student_id mapping
        existing_subnet_owners = {}  # subnet -> student_id mapping
        duplicate_ports = set()  # ports that are duplicated in CSV
        duplicate_subnets = set()  # subnets that are duplicated in CSV
        
        # Track which ports/subnets appear multiple times in CSV
        port_counts = {}
        subnet_counts = {}
        
        for existing in existing_students:
            if existing.get('port') and existing['port'] > 0:
                port = existing['port']
                port_counts[port] = port_counts.get(port, 0) + 1
                if port_counts[port] == 1:
                    existing_port_owners[port] = existing['student_id']
                else:
                    # This port appears multiple times - mark as duplicate
                    duplicate_ports.add(port)
                    
            if existing.get('subnet_id') and existing['subnet_id'] is not None:
                subnet = existing['subnet_id']
                subnet_counts[subnet] = subnet_counts.get(subnet, 0) + 1
                if subnet_counts[subnet] == 1:
                    existing_subnet_owners[subnet] = existing['student_id']
                else:
                    # This subnet appears multiple times - mark as duplicate
                    duplicate_subnets.add(subnet)
        
        # Track ports and subnets assigned within this batch to prevent duplicates
        assigned_ports_in_batch = set()
        assigned_subnets_in_batch = set()
        
        updated_students = []
        changes_made = False
        
        for student in students:
            updated_student = student.copy()
            
            # Ensure valid port assignment
            needs_new_port = False
            if not student.get('port') or student['port'] <= 0:
                needs_new_port = True
            elif student['port'] in assigned_ports_in_batch:
                # Port was already assigned to another student in this batch
                needs_new_port = True
            elif student['port'] in duplicate_ports:
                # Port appears multiple times in CSV - needs reassignment for all
                needs_new_port = True
            elif student['port'] in used_ports:
                # Port is in CSV - check if it's owned by this same student
                current_owner = existing_port_owners.get(student['port'])
                if current_owner != student['student_id']:
                    # Port is owned by a different student - needs reassignment
                    needs_new_port = True
            
            if needs_new_port:
                new_port = self.auto_assign_port(used_ports | assigned_ports_in_batch)
                assigned_ports_in_batch.add(new_port)
                used_ports.add(new_port)
                updated_student['port'] = new_port
                print(f"🔧 Assigned port {new_port} to student {student['student_id']}")
                changes_made = True
            else:
                assigned_ports_in_batch.add(student['port'])
                used_ports.add(student['port'])
            
            # Ensure valid subnet assignment
            needs_new_subnet = False
            if not student.get('subnet_id') or student['subnet_id'] is None:
                needs_new_subnet = True
            elif student['subnet_id'] in assigned_subnets_in_batch:
                # Subnet was already assigned to another student in this batch
                needs_new_subnet = True
            elif student['subnet_id'] in duplicate_subnets:
                # Subnet appears multiple times in CSV - needs reassignment for all
                needs_new_subnet = True
            elif student['subnet_id'] in used_subnets:
                # Subnet is in CSV - check if it's owned by this same student
                current_owner = existing_subnet_owners.get(student['subnet_id'])
                if current_owner != student['student_id']:
                    # Subnet is owned by a different student - needs reassignment
                    needs_new_subnet = True
            
            if needs_new_subnet:
                new_subnet = self.calculate_subnet_id(student['student_id'], used_subnets | assigned_subnets_in_batch)
                assigned_subnets_in_batch.add(new_subnet)
                used_subnets.add(new_subnet)
                updated_student['subnet_id'] = new_subnet
                print(f"🔧 Assigned subnet {new_subnet} to student {student['student_id']}")
                changes_made = True
            else:
                assigned_subnets_in_batch.add(student['subnet_id'])
                subnet_id = student['subnet_id']
                if subnet_id is not None:
                    used_subnets.add(subnet_id)
            
            updated_students.append(updated_student)
        
        # Write back to CSV if we made changes
        if changes_made:
            # Read all students from CSV to preserve others not in our list
            all_students = self.read_students_csv(csv_file, update_if_changed=False)
            
            # Update the students we processed
            student_lookup = {s['student_id']: s for s in updated_students}
            for i, student in enumerate(all_students):
                if student['student_id'] in student_lookup:
                    all_students[i] = student_lookup[student['student_id']]
            
            # Add any new students not already in CSV
            existing_ids = {s['student_id'] for s in all_students}
            for student in updated_students:
                if student['student_id'] not in existing_ids:
                    all_students.append(student)
            
            self.write_students_csv(csv_file, all_students)
        
        return updated_students
    
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
                    row = {
                        'student_id': student['student_id'],
                        'student_name': student['student_name'],
                        'port': student['port'],
                        'subnet_id': student['subnet_id']  # Use existing subnet_id, don't recalculate
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
        
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Expected columns: student_id, student_name, port (optional), subnet_id (optional)
                    student_id = row['student_id'].strip()
                    student_name = row['student_name'].strip()
                    
                    # Handle port assignment - more robust checking
                    port_value = ''
                    if 'port' in row and row['port'] is not None:
                        port_value = str(row['port']).strip()
                    
                    port = 0  # Default to 0 to indicate needs assignment
                    if port_value and port_value.isdigit() and int(port_value) > 0:
                        port = int(port_value)
                    
                    # Handle subnet_id - more robust checking
                    subnet_value = ''
                    if 'subnet_id' in row and row['subnet_id'] is not None:
                        subnet_value = str(row['subnet_id']).strip()
                    
                    subnet_id = None  # Default to None to indicate needs assignment
                    if subnet_value and subnet_value.isdigit() and int(subnet_value) > 0:
                        subnet_id = int(subnet_value)
                    
                    students.append({
                        'student_id': student_id,
                        'student_name': student_name,
                        'port': port,
                        'subnet_id': subnet_id
                    })
                    
            print(f"✅ Loaded {len(students)} students from {csv_file}")
            
            # Use centralized assignment service to ensure all assignments are valid
            if update_if_changed:
                students = self.ensure_assignments(students, csv_file)
            
            return students
        except FileNotFoundError:
            print(f"❌ CSV file {csv_file} not found")
            return []
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return []
    
    def get_student_from_csv(self, student_id: str, csv_file: str) -> Optional[StudentData]:
        """Get a single student's data from CSV by student_id."""
        students = self.read_students_csv(csv_file)
        for student in students:
            if student['student_id'] == student_id:
                return student
        return None

    def spin_up_student(self, student_id: str, student_name: str, port: int, subnet_id: Optional[int] = None, csv_file: str = "students.csv") -> bool:
        """Spin up containers for a specific student."""
        print(f"🚀 Spinning up containers for student: {student_name} ({student_id}) on port {port}")
        
        env = self.get_student_env(student_id, student_name, port, subnet_id, csv_file)
        
        try:
            # Use project name to isolate each student's containers
            command = [
                "docker", "compose", 
                "-f", self.compose_file
            ]
            
            command.extend([
                "-p", f"cyber-lab-{student_id}",  # Project name for isolation
                "up", "-d", "--no-build"  # Use pre-built images, don't rebuild per student
            ])
            
            self.run_command(command, env=env, capture_output=False)
            print(f"✅ Containers started for {student_name}")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to start containers for {student_name}")
            return False
    
    def spin_down_student(self, student_id: str, csv_file: str = "students.csv") -> bool:
        """Spin down containers for a specific student."""
        # Get student info from CSV
        student_info = self.get_student_from_csv(student_id, csv_file)
        if not student_info:
            print(f"❌ Student {student_id} not found in {csv_file}")
            return False
        
        env = self.get_student_env(student_id, student_info['student_name'], student_info['port'], student_info.get('subnet_id'), csv_file)
        print(f"🔽 Spinning down containers for student: {student_info['student_name']} ({student_id})")
        
        try:
            # Use project name to isolate each student's containers
            self.run_command([
                "docker", "compose", 
                "-f", self.compose_file,
                "-p", f"cyber-lab-{student_id}",  # Project name for isolation
                "down", "--volumes", "--remove-orphans"
            ], env=env, capture_output=False)
            print(f"✅ Containers removed for {student_info['student_name']}")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to remove containers for {student_info['student_name']}")
            return False

    def force_remove_student_containers(self, student_id: str) -> bool:
        """Force remove containers for a student ID without requiring CSV data.
        
        This is used during reconciliation to remove extra containers that are not in the CSV.
        """
        print(f"🔽 Force removing containers for student: {student_id}")
        
        try:
            # Set up basic environment variables for compose down
            # We don't have full student data, but we can provide the essential ones
            env = {
                "STUDENT_ID": student_id,
                "NETWORK_NAME": f"cyber-lab-{student_id}",  # Standard network name
            }

            # Use project name to remove containers with environment
            self.run_command([
                "docker", "compose", 
                "-f", self.compose_file,
                "-p", f"cyber-lab-{student_id}",  # Project name for isolation
                "down", "--volumes", "--remove-orphans"
            ], env=env, capture_output=False)
            print(f"✅ Containers removed for {student_id}")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to remove containers for {student_id}")
            return False
    
    def spin_up_class(self, csv_file: str, parallel: bool = True) -> bool:
        """Spin up containers for all students in the CSV file."""
        students = self.read_students_csv(csv_file)
        if not students:
            return False
        
        print(f"🚀 Spinning up containers for {len(students)} students...")
        
        # Add confirmation screen for parallel operations
        if parallel:
            parallel = self._confirm_parallel_execution("created")
        
        # For both parallel and sequential execution, ensure all assignments are complete
        # before starting container operations to avoid race conditions
        print("🔧 Ensuring all port and subnet assignments are complete...")
        students = self.ensure_assignments(students, csv_file)
        
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
                        student['subnet_id'],
                        csv_file
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
                    student['subnet_id'],
                    csv_file
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
        
        # Add confirmation screen for parallel operations
        if parallel:
            parallel = self._confirm_parallel_execution("stopped")
        
        if parallel:
            # Parallel execution
            success_count = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                future_to_student = {
                    executor.submit(self.spin_down_student, student['student_id'], csv_file): student 
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
                if self.spin_down_student(student['student_id'], csv_file):
                    success_count += 1
        
        print(f"✅ Successfully removed containers for {success_count}/{len(students)} students")
        return success_count == len(students)
    
    def get_running_students(self) -> Set[str]:
        """Get set of student IDs that currently have running containers."""
        try:
            # Look for containers with our project naming pattern (all containers, not just running)
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json"
            ])
            
            student_ids = set()
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        names = container.get('Names', '')
                        
                        # Extract student ID from container names
                        # Service containers are named: {service}-{student_id}
                        # Examples: kali-jump-student001, ubuntu-target1-student002, etc.
                        if names:
                            for name in names.split(','):
                                # Look for our service patterns
                                if any(service in name for service in ['kali-jump-', 'ubuntu-target1-', 'ubuntu-target2-']):
                                    # Extract student ID from the end of the name
                                    parts = name.split('-')
                                    if len(parts) >= 2:
                                        potential_id = parts[-1]  # Last part should be student ID
                                        # Accept any student ID that looks like an alphanumeric identifier
                                        # This includes: student001, test001, extratest001, debugtest001, etc.
                                        if potential_id and len(potential_id) >= 3:
                                            student_ids.add(potential_id)
            return student_ids
        except subprocess.CalledProcessError:
            print("❌ Failed to get running students")
            return set()
    
    def reconcile_with_csv(self, csv_file: str) -> bool:
        """Reconcile current Docker state with CSV file."""
        students = self.read_students_csv(csv_file)
        if not students:
            return False
        
        # Ensure all assignments are complete before reconciliation
        print("🔧 Ensuring all port and subnet assignments are complete...")
        students = self.ensure_assignments(students, csv_file)
        
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
                if not self.force_remove_student_containers(student_id):
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
                    student_data['subnet_id'],
                    csv_file
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
        
        # Ensure assignments are complete for this student
        print(f"🔧 Ensuring assignments are complete for student {student_id}...")
        updated_students = self.ensure_assignments([student_data], csv_file)
        updated_student = updated_students[0]
        
        return self.spin_up_student(
            updated_student['student_id'],
            updated_student['student_name'],
            updated_student['port'],
            updated_student['subnet_id'],
            csv_file
        )
    
    def recreate_student(self, student_id: str, csv_file: str) -> bool:
        students = self.read_students_csv(csv_file)
        student_data = next((s for s in students if s['student_id'] == student_id), None)
        
        if not student_data:
            print(f"❌ Student {student_id} not found in CSV file")
            return False
        
        print(f"🔄 Recreating containers for student: {student_data['student_name']} ({student_id})")
        
        # Ensure assignments are complete for this student
        print(f"🔧 Ensuring assignments are complete for student {student_id}...")
        updated_students = self.ensure_assignments([student_data], csv_file)
        updated_student = updated_students[0]
        
        # First spin down
        self.spin_down_student(student_id)
        
        # Then spin up
        return self.spin_up_student(
            updated_student['student_id'],
            updated_student['student_name'],
            updated_student['port'],
            updated_student['subnet_id'],
            csv_file
        )
    
    def list_student_containers(self, student_id: str) -> List[Dict[str, str]]:
        """List all containers for a specific student."""
        try:
            # Look for all containers, then filter by student ID
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json"
            ])
            
            containers: List[Dict[str, str]] = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        names = container.get('Names', '')
                        
                        # Check if this container belongs to the student
                        if names and student_id in names:
                            containers.append(container)
            
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
            # Get all containers and filter for lab-related ones
            result = self.run_command([
                "docker", "ps", "-a", "--format", "json"
            ])
            
            if not result.stdout.strip():
                print("No containers found")
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
                            # Look for student IDs in various naming patterns
                            if 'student' in name:
                                parts = name.split('-')
                                for part in parts:
                                    if part.startswith('student') and part[7:].isdigit():
                                        student_id = part
                                        break
                                if student_id:
                                    break
                    
                    if student_id:
                        if student_id not in students:
                            students[student_id] = []
                        students[student_id].append(container)
            
            if not students:
                print("No lab containers found")
                return
            
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
            "ubuntu1": "ubuntu-target1"
        }
        
        if container_type not in service_map:
            print(f"❌ Invalid container type: {container_type}")
            print("Valid types: kali, ubuntu1")
            return
        
        # Containers are named: {service}-{student_id}
        container_name = f"{service_map[container_type]}-{student_id}"
        
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
    
    recreate_parser = student_subparsers.add_parser("recreate", help="Recreate student containers")
    recreate_parser.add_argument("student_id", help="Student ID")
    recreate_parser.add_argument("csv_file", help="CSV file with student data")
    
    status_parser = student_subparsers.add_parser("status", help="Show student container status")
    status_parser.add_argument("student_id", help="Student ID")
    
    exec_parser = student_subparsers.add_parser("exec", help="Execute into student container")
    exec_parser.add_argument("student_id", help="Student ID")
    exec_parser.add_argument("--container", choices=["kali", "ubuntu1"], 
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
        if args.student_action == "recreate":
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
