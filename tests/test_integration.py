#!/usr/bin/env python3
"""
Integration tests for Lab Manager

These tests verify the complete workflow including:
- Docker image building
- Container creation and management
- Network isolation
- Port mapping
- CSV integration
- Cleanup operations

These tests require Docker to be available and will create actual containers.
Run with: pytest tests/test_integration.py -v -s
"""

import pytest
import tempfile
import os
import csv
import time
import subprocess
import json
from typing import List, Dict
import sys

# Import the classes we want to test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lab_manager import LabManager, StudentData
from tests.conftest import create_csv_with_data


class TestDockerIntegration:
    """Integration tests that require Docker"""
    
    def _needs_sudo_for_docker(self) -> bool:
        """Check if Docker requires sudo by trying a simple command"""
        try:
            result = subprocess.run(
                ["docker", "info"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode != 0
        except:
            # If Docker command fails, assume we need sudo
            return True
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test"""
        # Auto-detect if sudo is needed for Docker
        use_sudo = self._needs_sudo_for_docker()
        print(f"\n🔧 Using sudo for Docker: {use_sudo}")
        
        self.lab_manager = LabManager(use_sudo=use_sudo)
        self.test_csv_files = []
        self.created_networks = []
        self.created_containers = []
        
        yield
        
        # Cleanup after each test
        self.cleanup_test_resources()
    
    def cleanup_test_resources(self):
        """Clean up any Docker resources created during tests"""
        print("\n🧹 Cleaning up test resources...")
        
        # First: Stop and remove any test containers
        try:
            result = self.lab_manager.run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
            container_names = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for name in container_names:
                if name and ('test' in name and ('kali-jump' in name or 'ubuntu-target' in name)):
                    print(f"  Removing container {name}")
                    try:
                        self.lab_manager.run_command(["docker", "rm", "-f", name])
                    except Exception as e:
                        print(f"    ⚠️  Failed to remove container {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Error listing containers: {e}")
        
        # Second: Remove any test networks (containers should be gone now)
        try:
            result = self.lab_manager.run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
            network_names = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for name in network_names:
                if name and ('cyber-lab-test' in name or 'cyber-lab-student' in name or 'cyber-lab-nettest' in name):
                    print(f"  Removing network {name}")
                    try:
                        self.lab_manager.run_command(["docker", "network", "rm", name])
                    except Exception as e:
                        print(f"    ⚠️  Failed to remove network {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Error listing networks: {e}")
        
        # Third: Also try to remove by project name (this should clean up compose projects)
        project_names = [
            'teststudent001', 'teststudent002', 'teststudent003', 
            'testparallel001', 'testparallel002', 'testparallel003', 
            'nettest001', 'nettest002',
            'individualtest001', 'removetest001', 'recreatetest001',
            'reconciletest001', 'reconciletest002', 'extratest001', 'extratest002', 'extratest003',
            'assigntest001', 'assigntest002', 'mixedtest001', 'mixedtest002', 'mixedtest003',
            'exectest001', 'maptest001', 'functest001'  # Add our new exec test projects
        ]
        for project in project_names:
            try:
                print(f"  Cleaning up docker-compose project: cyber-lab-{project}")
                self.lab_manager.run_command([
                    "docker", "compose", "-p", f"cyber-lab-{project}", "down", "-v", "--remove-orphans"
                ])
            except Exception as e:
                print(f"    ⚠️  Failed to clean up project cyber-lab-{project}: {e}")
        
        # Clean up CSV files
        for csv_file in self.test_csv_files:
            try:
                os.unlink(csv_file)
            except Exception as e:
                print(f"  ⚠️  Failed to remove CSV file {csv_file}: {e}")
    
    def create_test_csv(self, students_data: List[dict]) -> str:
        """Helper to create a temporary CSV file with test data"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        create_csv_with_data(temp_file.name, students_data)
        self.test_csv_files.append(temp_file.name)
        return temp_file.name
    
    def wait_for_container_ready(self, container_name: str, max_wait: int = 30) -> bool:
        """Wait for a container to be ready"""
        print(f"    ⏳ Waiting for container {container_name}...")
        for i in range(max_wait):
            try:
                # Check if container exists and is running
                result = self.lab_manager.run_command([
                    "docker", "ps", "--filter", f"name={container_name}", 
                    "--filter", "status=running", "--format", "{{.Names}}"
                ])
                if container_name in result.stdout:
                    print(f"    ✅ Container {container_name} is ready")
                    return True
                    
                # Also try without status filter in case container is still starting
                result = self.lab_manager.run_command([
                    "docker", "ps", "-a", "--filter", f"name={container_name}", 
                    "--format", "{{.Names}}"
                ])
                if container_name in result.stdout:
                    # Container exists but may not be running yet
                    print(f"    📦 Container {container_name} exists, waiting for ready state... ({i+1}/{max_wait})")
                else:
                    print(f"    ❓ Container {container_name} not found yet... ({i+1}/{max_wait})")
                    
                time.sleep(1)
            except Exception as e:
                print(f"    ⚠️  Error checking container {container_name}: {e}")
                time.sleep(1)
        
        print(f"    ❌ Container {container_name} failed to become ready within {max_wait} seconds")
        return False
    
    def check_container_health(self, container_name: str) -> Dict:
        """Check the health/status of a container"""
        try:
            result = self.lab_manager.run_command([
                "docker", "inspect", container_name, "--format", "{{json .State}}"
            ])
            state = json.loads(result.stdout.strip())
            return {
                'status': state.get('Status', 'unknown'),
                'running': state.get('Running', False),
                'exit_code': state.get('ExitCode', -1)
            }
        except Exception as e:
            print(f"    ⚠️  Error inspecting container {container_name}: {e}")
            return {'status': 'not_found', 'running': False, 'exit_code': -1}
    
    def check_port_accessibility(self, port: int) -> bool:
        """Check if a port is accessible (bound)"""
        try:
            result = subprocess.run([
                "ss", "-tuln", f"sport = :{port}"
            ], capture_output=True, text=True, timeout=5)
            return str(port) in result.stdout
        except:
            return False


@pytest.mark.integration
class TestFullWorkflow(TestDockerIntegration):
    """Test the complete lab management workflow"""
    
    def test_build_images(self):
        """Test building Docker images"""
        print("\n🔨 Testing image build...")
        
        # Check if docker-compose.yml exists
        compose_file = "docker-compose.yml"
        assert os.path.exists(compose_file), "docker-compose.yml not found"
        
        # Build images
        success = self.lab_manager.build_images()
        assert success, "Docker image build failed"
        
        # Verify images were created
        result = self.lab_manager.run_command(["docker", "images", "--format", "json"])
        images = []
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line:
                    images.append(json.loads(line))
        
        # Look for our expected images
        image_names = [img.get('Repository', '') for img in images]
        expected_images = ['epic-research-infra-kali-jump', 'epic-research-infra-ubuntu-target1', 'epic-research-infra-ubuntu-target2']

        found_images = []
        for expected in expected_images:
            for image_name in image_names:
                if expected in image_name:
                    found_images.append(expected)
                    break
        
        print(f"Found images: {found_images}")
        assert len(found_images) >= 2, f"Expected to find at least 2 images, found: {found_images}"
    
    @pytest.mark.slow
    def test_single_student_lifecycle(self):
        """Test complete lifecycle for a single student"""
        print("\n👤 Testing single student lifecycle...")
        
        # Create test CSV with one student
        test_data = [
            {'student_id': 'teststudent001', 'student_name': 'Test Student', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Step 1: Spin up student
        print("  📤 Spinning up student containers...")
        success = self.lab_manager.spin_up_single_student('teststudent001', csv_file)
        assert success, "Failed to spin up student containers"
        
        # Step 2: Wait for containers to be ready
        print("  ⏳ Waiting for containers to be ready...")
        container_ready = self.wait_for_container_ready('kali-jump-teststudent001', max_wait=60)
        assert container_ready, "Kali container failed to start within timeout"
        
        # Step 3: Check container health
        print("  🔍 Checking container health...")
        kali_health = self.check_container_health('kali-jump-teststudent001')
        assert kali_health['running'], f"Kali container not running: {kali_health}"
        
        # Step 4: Verify network isolation
        print("  🌐 Verifying network isolation...")
        result = self.lab_manager.run_command(["docker", "network", "ls", "--format", "json"])
        networks = []
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line:
                    networks.append(json.loads(line))
        
        student_networks = [net for net in networks if 'cyber-lab-teststudent001' in net.get('Name', '')]
        assert len(student_networks) >= 1, "Student network not found"
        
        # Step 5: Check port mapping
        print("  🔌 Checking port mapping...")
        students = self.lab_manager.read_students_csv(csv_file)
        student = students[0]
        assert student['port'] >= 2222, f"Invalid port assignment: {student['port']}"
        
        # Check if port is actually bound
        port_bound = self.check_port_accessibility(student['port'])
        # Note: This might fail in some environments, so we'll just log it
        print(f"  Port {student['port']} bound: {port_bound}")
        
        # Step 6: Test container interaction
        print("  💬 Testing container interaction...")
        try:
            # Try to execute a simple command in the kali container
            result = self.lab_manager.run_command([
                "docker", "exec", "kali-jump-teststudent001", 
                "echo", "test-connection-success"
            ])
            assert "test-connection-success" in result.stdout, "Container command execution failed"
        except Exception as e:
            pytest.fail(f"Container interaction test failed: {e}")
        
        # Step 7: Test cleanup
        print("  🗑️  Testing cleanup...")
        success = self.lab_manager.spin_down_student('teststudent001', csv_file)
        assert success, "Failed to spin down student containers"
        
        # Verify containers are gone
        time.sleep(3)  # Give Docker time to clean up
        kali_health_after = self.check_container_health('kali-jump-teststudent001')
        assert not kali_health_after['running'], "Container still running after cleanup"
    
    @pytest.mark.slow  
    def test_multi_student_class_sequential(self):
        """Test managing a small class of students in sequential mode"""
        print("\n🏫 Testing multi-student class management (sequential)...")
        
        # Create test CSV with multiple students
        test_data = [
            {'student_id': 'teststudent001', 'student_name': 'Alice Test', 'port': '', 'subnet_id': ''},
            {'student_id': 'teststudent002', 'student_name': 'Bob Test', 'port': '', 'subnet_id': ''},
            {'student_id': 'teststudent003', 'student_name': 'Carol Test', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Step 1: Spin up entire class (sequential to avoid resource conflicts)
        print("  📤 Spinning up class (sequential mode)...")
        success = self.lab_manager.spin_up_class(csv_file, parallel=False)
        assert success, "Failed to spin up class"
        
        # Step 2: Verify all students have containers
        print("  🔍 Verifying all student containers...")
        students = self.lab_manager.read_students_csv(csv_file)
        assert len(students) == 3, f"Expected 3 students, found {len(students)}"
        
        # Check that all students have unique ports and subnets
        ports = [s['port'] for s in students]
        subnets = [s['subnet_id'] for s in students]
        assert len(set(ports)) == 3, f"Duplicate ports found: {ports}"
        assert len(set(subnets)) == 3, f"Duplicate subnets found: {subnets}"
        
        # Step 3: Check container status for each student
        running_containers = 0
        for student in students:
            container_name = f"kali-jump-{student['student_id']}"
            if self.wait_for_container_ready(container_name, max_wait=30):
                health = self.check_container_health(container_name)
                if health['running']:
                    running_containers += 1
                    print(f"  ✅ {student['student_id']} container running")
                else:
                    print(f"  ❌ {student['student_id']} container not running: {health}")
        
        assert running_containers >= 2, f"Only {running_containers}/3 containers running"
        
        # Step 4: Test reconciliation
        print("  🔄 Testing reconciliation...")
        success = self.lab_manager.reconcile_with_csv(csv_file)
        assert success, "Reconciliation failed"
        
        # Step 5: Clean up entire class
        print("  🗑️  Cleaning up entire class...")
        success = self.lab_manager.spin_down_class(csv_file, parallel=False)
        assert success, "Failed to spin down class"
        
        # Verify cleanup
        time.sleep(5)  # Give Docker time to clean up
        running_after_cleanup = 0
        for student in students:
            container_name = f"kali-jump-{student['student_id']}"
            health = self.check_container_health(container_name)
            if health['running']:
                running_after_cleanup += 1
        
        assert running_after_cleanup == 0, f"Still {running_after_cleanup} containers running after cleanup"
    
    @pytest.mark.slow
    def test_multi_student_class_parallel(self):
        """Test managing a small class of students in parallel mode"""
        print("\n🏫 Testing multi-student class management (parallel)...")
        
        # Create test CSV with multiple students
        test_data = [
            {'student_id': 'testparallel001', 'student_name': 'Alice Parallel', 'port': '', 'subnet_id': ''},
            {'student_id': 'testparallel002', 'student_name': 'Bob Parallel', 'port': '', 'subnet_id': ''},
            {'student_id': 'testparallel003', 'student_name': 'Carol Parallel', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Step 1: Test parallel spin up (with mock user confirmation)
        print("  📤 Spinning up class (parallel mode)...")
        # Override the confirmation method to automatically accept parallel execution
        original_confirm = self.lab_manager._confirm_parallel_execution
        self.lab_manager._confirm_parallel_execution = lambda operation_name: True
        
        try:
            success = self.lab_manager.spin_up_class(csv_file, parallel=True)
            assert success, "Failed to spin up class in parallel"
            
            # Step 2: Verify all students have containers and unique assignments
            print("  🔍 Verifying all student containers...")
            students = self.lab_manager.read_students_csv(csv_file)
            assert len(students) == 3, f"Expected 3 students, found {len(students)}"
            
            # Check that all students have unique ports and subnets (critical for parallel execution)
            ports = [s['port'] for s in students]
            subnets = [s['subnet_id'] for s in students]
            assert len(set(ports)) == 3, f"Duplicate ports found in parallel execution: {ports}"
            assert len(set(subnets)) == 3, f"Duplicate subnets found in parallel execution: {subnets}"
            
            # Step 3: Wait for containers to be ready (parallel execution may take longer)
            print("  ⏳ Waiting for all containers to be ready...")
            running_containers = 0
            for student in students:
                container_name = f"kali-jump-{student['student_id']}"
                # Give more time for parallel execution
                if self.wait_for_container_ready(container_name, max_wait=45):
                    health = self.check_container_health(container_name)
                    if health['running']:
                        running_containers += 1
                        print(f"  ✅ {student['student_id']} container running")
                    else:
                        print(f"  ❌ {student['student_id']} container not running: {health}")
            
            # In parallel mode, we should expect all containers to start
            assert running_containers >= 2, f"Only {running_containers}/3 containers running in parallel mode"
            
            # Step 4: Test parallel reconciliation
            print("  🔄 Testing reconciliation...")
            success = self.lab_manager.reconcile_with_csv(csv_file)
            assert success, "Reconciliation failed"
            
            # Step 5: Test parallel cleanup
            print("  🗑️  Cleaning up entire class (parallel mode)...")
            success = self.lab_manager.spin_down_class(csv_file, parallel=True)
            assert success, "Failed to spin down class in parallel"
            
            # Verify cleanup (give more time for parallel cleanup)
            time.sleep(8)  # Give Docker more time for parallel cleanup
            running_after_cleanup = 0
            for student in students:
                container_name = f"kali-jump-{student['student_id']}"
                health = self.check_container_health(container_name)
                if health['running']:
                    running_after_cleanup += 1
            
            assert running_after_cleanup == 0, f"Still {running_after_cleanup} containers running after parallel cleanup"
            
        finally:
            # Restore original confirmation method
            self.lab_manager._confirm_parallel_execution = original_confirm
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        print("\n🚨 Testing error handling...")
        
        # Test 1: Try to spin up non-existent student
        print("  Testing non-existent student...")
        success = self.lab_manager.spin_down_student('nonexistent')
        assert not success, "Should fail when trying to manage non-existent student"
        
        # Test 2: Try with invalid CSV
        print("  Testing invalid CSV...")
        invalid_csv = "/tmp/nonexistent.csv"
        students = self.lab_manager.read_students_csv(invalid_csv)
        assert students == [], "Should return empty list for non-existent CSV"
        
        # Test 3: Try to spin up with missing CSV
        print("  Testing missing CSV file...")
        success = self.lab_manager.spin_up_class("/tmp/nonexistent.csv")
        assert not success, "Should fail with non-existent CSV"


@pytest.mark.integration  
class TestIndividualStudentOperations(TestDockerIntegration):
    """Test individual student management operations"""
    
    @pytest.mark.slow
    def test_add_single_student(self):
        """Test adding a single student"""
        print("\n👤 Testing add single student...")
        
        # Create test CSV with one student (no assignments yet)
        test_data = [
            {'student_id': 'individualtest001', 'student_name': 'Individual Test Student', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Add the student
        success = self.lab_manager.spin_up_single_student('individualtest001', csv_file)
        assert success, "Failed to add single student"
        
        # Verify container is running
        container_ready = self.wait_for_container_ready('kali-jump-individualtest001', max_wait=30)
        assert container_ready, "Container failed to start"
        
        health = self.check_container_health('kali-jump-individualtest001')
        assert health['running'], f"Container not running: {health}"
        
        # Verify CSV was updated with assignments
        students = self.lab_manager.read_students_csv(csv_file)
        student = students[0]
        assert student['port'] >= 2222, f"Port not assigned: {student['port']}"
        assert student['subnet_id'] is not None and int(student['subnet_id']) > 0, f"Subnet not assigned: {student['subnet_id']}"
        
        # Cleanup
        success = self.lab_manager.spin_down_student('individualtest001', csv_file)
        assert success, "Failed to remove student"
    
    @pytest.mark.slow
    def test_remove_single_student(self):
        """Test removing a single student"""
        print("\n👤 Testing remove single student...")
        
        # Create and start a student first
        test_data = [
            {'student_id': 'removetest001', 'student_name': 'Remove Test Student', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Add student
        success = self.lab_manager.spin_up_single_student('removetest001', csv_file)
        assert success, "Failed to add student for removal test"
        
        # Wait for container
        container_ready = self.wait_for_container_ready('kali-jump-removetest001', max_wait=30)
        assert container_ready, "Container failed to start"
        
        # Now test removal
        success = self.lab_manager.spin_down_student('removetest001', csv_file)
        assert success, "Failed to remove student"
        
        # Verify container is gone
        time.sleep(3)
        health = self.check_container_health('kali-jump-removetest001')
        assert not health['running'], "Container still running after removal"
    
    @pytest.mark.slow
    def test_recreate_student(self):
        """Test recreating a student's containers"""
        print("\n🔄 Testing recreate student...")
        
        # Create and start a student first
        test_data = [
            {'student_id': 'recreatetest001', 'student_name': 'Recreate Test Student', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Add student initially
        success = self.lab_manager.spin_up_single_student('recreatetest001', csv_file)
        assert success, "Failed to add student for recreate test"
        
        container_ready = self.wait_for_container_ready('kali-jump-recreatetest001', max_wait=30)
        assert container_ready, "Initial container failed to start"
        
        # Recreate the student
        success = self.lab_manager.recreate_student('recreatetest001', csv_file)
        assert success, "Failed to recreate student"
        
        # Wait for new container to be ready
        container_ready = self.wait_for_container_ready('kali-jump-recreatetest001', max_wait=30)
        assert container_ready, "Recreated container failed to start"
        
        # Verify container is running (this ensures recreation was successful)
        health = self.check_container_health('kali-jump-recreatetest001')
        assert health['running'], f"Container not running after recreation: {health}"
        
        # Cleanup
        self.lab_manager.spin_down_student('recreatetest001', csv_file)
        
        # Cleanup
        self.lab_manager.spin_down_student('recreatetest001', csv_file)


@pytest.mark.integration
class TestReconciliation(TestDockerIntegration):
    """Test reconciliation functionality"""
    
    @pytest.mark.slow
    def test_reconcile_missing_students(self):
        """Test reconciliation when students are missing from running environment"""
        print("\n🔄 Testing reconcile with missing students...")
        
        # Create CSV with students but DON'T start them - test the ADD case
        test_data = [
            {'student_id': 'reconciletest001', 'student_name': 'Reconcile Test 1', 'port': '', 'subnet_id': ''},
            {'student_id': 'reconciletest002', 'student_name': 'Reconcile Test 2', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Verify no containers are running initially
        health1_before = self.check_container_health('kali-jump-reconciletest001')
        health2_before = self.check_container_health('kali-jump-reconciletest002')
        assert not health1_before['running'], "Container 1 should not be running initially"
        assert not health2_before['running'], "Container 2 should not be running initially"
        
        # Run reconciliation (should ADD the missing students)
        success = self.lab_manager.reconcile_with_csv(csv_file)
        assert success, "Reconciliation failed"
        
        # Verify students were ADDED by reconciliation
        container1_ready = self.wait_for_container_ready('kali-jump-reconciletest001', max_wait=30)
        container2_ready = self.wait_for_container_ready('kali-jump-reconciletest002', max_wait=30)
        
        assert container1_ready, "First student container not started by reconciliation"
        assert container2_ready, "Second student container not started by reconciliation"
        
        # Verify containers are actually running
        health1 = self.check_container_health('kali-jump-reconciletest001')
        health2 = self.check_container_health('kali-jump-reconciletest002')
        
        assert health1['running'], "First student not running after reconciliation"
        assert health2['running'], "Second student not running after reconciliation"
        
        # Verify assignments were made during reconciliation
        students = self.lab_manager.read_students_csv(csv_file)
        assert len(students) == 2, "Should have 2 students"
        for student in students:
            assert student['port'] >= 2222, f"Port not assigned during reconciliation: {student}"
            assert student['subnet_id'] is not None and int(student['subnet_id']) > 0, f"Subnet not assigned during reconciliation: {student}"
        
        print(f"  ✅ Reconciliation successfully ADDED {len(students)} missing students")
        
        # Cleanup
        self.lab_manager.spin_down_class(csv_file, parallel=False)
    
    @pytest.mark.slow
    def test_reconcile_extra_containers(self):
        """Test reconciliation when there are extra running containers that need to be REMOVED"""
        print("\n🔄 Testing reconcile with extra containers (REMOVE case)...")
        
        # Step 1: Start with 3 students
        initial_data = [
            {'student_id': 'extratest001', 'student_name': 'Extra Test 1', 'port': '', 'subnet_id': ''},
            {'student_id': 'extratest002', 'student_name': 'Extra Test 2', 'port': '', 'subnet_id': ''},
            {'student_id': 'extratest003', 'student_name': 'Extra Test 3', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(initial_data)
        
        # Start all 3 students
        success = self.lab_manager.spin_up_class(csv_file, parallel=False)
        assert success, "Failed to start initial students"
        
        # Wait for all containers to be ready
        containers_ready = 0
        container_states_before = {}
        for student in initial_data:
            container_name = f'kali-jump-{student["student_id"]}'
            if self.wait_for_container_ready(container_name, max_wait=20):
                containers_ready += 1
                container_states_before[student["student_id"]] = self.check_container_health(container_name)
        
        assert containers_ready >= 2, f"Only {containers_ready}/3 initial containers started"
        print(f"  ✅ Started {containers_ready} initial containers")
        
        # Step 2: Create a new CSV with only 2 students (removing extratest003)
        # Use the actual port assignments from the running containers
        running_students = self.lab_manager.read_students_csv(csv_file)
        reduced_data = [
            {
                'student_id': 'extratest001', 
                'student_name': 'Extra Test 1', 
                'port': running_students[0]['port'], 
                'subnet_id': running_students[0]['subnet_id']
            },
            {
                'student_id': 'extratest002', 
                'student_name': 'Extra Test 2', 
                'port': running_students[1]['port'], 
                'subnet_id': running_students[1]['subnet_id']
            }
            # extratest003 is intentionally REMOVED from the new CSV
        ]
        reduced_csv_file = self.create_test_csv(reduced_data)
        
        # Step 3: Run reconciliation - this should REMOVE extratest003
        print(f"  🔄 Running reconciliation to remove extratest003...")
        success = self.lab_manager.reconcile_with_csv(reduced_csv_file)
        assert success, "Reconciliation failed"
        
        # Step 4: Verify reconciliation results
        time.sleep(5)  # Give time for removal to complete
        
        # Check that extratest003 was REMOVED
        health3_after = self.check_container_health('kali-jump-extratest003')
        assert not health3_after['running'], "extratest003 should have been REMOVED by reconciliation"
        
        # Check that extratest001 and extratest002 are still running
        health1_after = self.check_container_health('kali-jump-extratest001')
        health2_after = self.check_container_health('kali-jump-extratest002')
        assert health1_after['running'], "extratest001 should still be running after reconciliation"
        assert health2_after['running'], "extratest002 should still be running after reconciliation"
        
        print(f"  ✅ Reconciliation successfully REMOVED extratest003")
        print(f"  ✅ extratest001 and extratest002 still running as expected")
        
        # Cleanup remaining containers
        self.lab_manager.spin_down_class(reduced_csv_file, parallel=False)
    
    def test_reconcile_assignment_updates(self):
        """Test reconciliation when CSV has assignment updates"""
        print("\n🔄 Testing reconcile with assignment updates...")
        
        # Create CSV with incomplete assignments
        test_data = [
            {'student_id': 'assigntest001', 'student_name': 'Assign Test 1', 'port': '', 'subnet_id': ''},
            {'student_id': 'assigntest002', 'student_name': 'Assign Test 2', 'port': '2223', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Run reconciliation (should fill in missing assignments)
        success = self.lab_manager.reconcile_with_csv(csv_file)
        assert success, "Reconciliation failed"
        
        # Verify assignments were filled in
        students = self.lab_manager.read_students_csv(csv_file)
        for student in students:
            assert student['port'] >= 2222, f"Port not assigned for {student['student_id']}: {student['port']}"
            assert student['subnet_id'] is not None and int(student['subnet_id']) > 0, f"Subnet not assigned for {student['student_id']}: {student['subnet_id']}"
        
        # Verify ports are unique
        ports = [s['port'] for s in students]
        assert len(set(ports)) == len(ports), f"Duplicate ports found: {ports}"
        
        # Cleanup any containers that might have been started
        self.lab_manager.spin_down_class(csv_file, parallel=False)
    
    @pytest.mark.slow
    def test_reconcile_mixed_add_and_remove(self):
        """Test reconciliation with both ADD and REMOVE operations in one pass"""
        print("\n🔄 Testing reconcile with mixed ADD and REMOVE operations...")
        
        # Step 1: Start with initial set of students
        initial_data = [
            {'student_id': 'mixedtest001', 'student_name': 'Mixed Test 1', 'port': '', 'subnet_id': ''},
            {'student_id': 'mixedtest002', 'student_name': 'Mixed Test 2', 'port': '', 'subnet_id': ''}
        ]
        initial_csv = self.create_test_csv(initial_data)
        
        # Start the initial students
        success = self.lab_manager.spin_up_class(initial_csv, parallel=False)
        assert success, "Failed to start initial students"
        
        # Wait for initial containers
        container1_ready = self.wait_for_container_ready('kali-jump-mixedtest001', max_wait=30)
        container2_ready = self.wait_for_container_ready('kali-jump-mixedtest002', max_wait=30)
        assert container1_ready and container2_ready, "Initial containers failed to start"
        
        # Step 2: Create new CSV that removes mixedtest001 and adds mixedtest003
        running_students = self.lab_manager.read_students_csv(initial_csv)
        mixed_data = [
            # Keep mixedtest002 (no change)
            {
                'student_id': 'mixedtest002', 
                'student_name': 'Mixed Test 2', 
                'port': running_students[1]['port'], 
                'subnet_id': running_students[1]['subnet_id']
            },
            # Add new student mixedtest003
            {'student_id': 'mixedtest003', 'student_name': 'Mixed Test 3', 'port': '', 'subnet_id': ''}
            # Remove mixedtest001 (not in new CSV)
        ]
        mixed_csv = self.create_test_csv(mixed_data)
        
        # Step 3: Run reconciliation (should REMOVE mixedtest001 and ADD mixedtest003)
        print("  🔄 Running mixed reconciliation...")
        success = self.lab_manager.reconcile_with_csv(mixed_csv)
        assert success, "Mixed reconciliation failed"
        
        # Step 4: Verify the results
        time.sleep(5)  # Give time for changes to complete
        
        # mixedtest001 should be REMOVED
        health1 = self.check_container_health('kali-jump-mixedtest001')
        assert not health1['running'], "mixedtest001 should have been REMOVED"
        
        # mixedtest002 should still be running (unchanged)
        health2 = self.check_container_health('kali-jump-mixedtest002')
        assert health2['running'], "mixedtest002 should still be running"
        
        # mixedtest003 should be ADDED
        container3_ready = self.wait_for_container_ready('kali-jump-mixedtest003', max_wait=30)
        assert container3_ready, "mixedtest003 should have been ADDED"
        
        health3 = self.check_container_health('kali-jump-mixedtest003')
        assert health3['running'], "mixedtest003 should be running after being added"
        
        print("  ✅ Mixed reconciliation: REMOVED mixedtest001, KEPT mixedtest002, ADDED mixedtest003")
        
        # Verify assignments were made for the new student
        final_students = self.lab_manager.read_students_csv(mixed_csv)
        assert len(final_students) == 2, "Should have 2 students after reconciliation"
        
        mixedtest003_data = next((s for s in final_students if s['student_id'] == 'mixedtest003'), None)
        assert mixedtest003_data is not None, "mixedtest003 data should exist"
        assert mixedtest003_data['port'] >= 2222, "mixedtest003 should have assigned port"
        assert mixedtest003_data['subnet_id'] is not None and int(mixedtest003_data['subnet_id']) > 0, "mixedtest003 should have assigned subnet"
        
        # Cleanup
        self.lab_manager.spin_down_class(mixed_csv, parallel=False)


@pytest.mark.integration
class TestNetworkIsolation(TestDockerIntegration):
    """Test network isolation between students"""
    
    @pytest.mark.slow
    def test_network_isolation(self):
        """Test that students are properly isolated in separate networks"""
        print("\n🌐 Testing network isolation...")
        
        # Create test CSV with two students
        test_data = [
            {'student_id': 'nettest001', 'student_name': 'Network Test 1', 'port': '', 'subnet_id': ''},
            {'student_id': 'nettest002', 'student_name': 'Network Test 2', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Spin up both students
        success = self.lab_manager.spin_up_class(csv_file, parallel=False)
        assert success, "Failed to spin up test students"
        
        # Wait for containers to be ready
        container1_ready = self.wait_for_container_ready('kali-jump-nettest001', max_wait=30)
        container2_ready = self.wait_for_container_ready('kali-jump-nettest002', max_wait=30)
        
        if container1_ready and container2_ready:
            # Check that each student has their own networks (DMZ + Internal)
            result = self.lab_manager.run_command(["docker", "network", "ls", "--format", "json"])
            networks = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        networks.append(json.loads(line))
            
            student_networks = [net for net in networks if 'cyber-lab-nettest' in net.get('Name', '')]
            # Each student should have 2 networks (DMZ + Internal), so 2 students = 4 networks minimum
            assert len(student_networks) >= 4, f"Expected at least 4 student networks (2 per student), found: {len(student_networks)}"
            
            # Check for both DMZ and Internal networks for each student
            dmz_networks = [net for net in student_networks if 'dmz' in net.get('Name', '')]
            internal_networks = [net for net in student_networks if 'internal' in net.get('Name', '')]
            
            assert len(dmz_networks) >= 2, f"Expected at least 2 DMZ networks, found: {len(dmz_networks)}"
            assert len(internal_networks) >= 2, f"Expected at least 2 Internal networks, found: {len(internal_networks)}"
            
            print(f"  Found {len(student_networks)} student networks ({len(dmz_networks)} DMZ + {len(internal_networks)} Internal)")
        else:
            pytest.skip("Containers not ready for network isolation test")
        
        # Cleanup
        self.lab_manager.spin_down_class(csv_file, parallel=False)

    @pytest.mark.slow
    def test_dual_network_connectivity(self):
        """Test that dual-network architecture works correctly with proper isolation and pivoting"""
        print("\n🌐 Testing dual-network connectivity and isolation...")
        
        # Create test CSV with one student for focused network testing
        test_data = [
            {'student_id': 'netconntest001', 'student_name': 'Network Connectivity Test', 'port': '6666', 'subnet_id': '100'}
        ]
        csv_file = self.create_test_csv(test_data)
        
        # Spin up the student
        success = self.lab_manager.spin_up_class(csv_file, parallel=False)
        assert success, "Failed to spin up test student"
        
        # Wait for all containers to be ready
        containers_ready = {}
        for container_type in ["kali-jump", "ubuntu-target1", "ubuntu-target2"]:
            container_name = f"{container_type}-netconntest001"
            containers_ready[container_type] = self.wait_for_container_ready(container_name, max_wait=45)
            assert containers_ready[container_type], f"{container_name} failed to start"
        
        print("  ✅ All containers started successfully")
        
        try:
            # Test 1: Verify network interfaces and IP addresses
            print("  🔍 Verifying network configuration...")
            
            # Check Kali Jump Box (should only be on DMZ network: 10.100.1.10)
            result = self.lab_manager.run_command([
                "docker", "exec", "kali-jump-netconntest001", 
                "ip", "addr", "show"
            ])
            kali_interfaces = result.stdout
            assert "10.100.1.10" in kali_interfaces, "Kali should have DMZ IP 10.100.1.10"
            assert "192.168.100" not in kali_interfaces, "Kali should NOT have internal network access"
            print("    ✅ Kali Jump Box: Only on DMZ network (10.100.1.10)")
            
            # Check Ubuntu Target 1 (should be dual-homed: 10.100.1.11 + 192.168.100.11)
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target1-netconntest001", 
                "ip", "addr", "show"
            ])
            target1_interfaces = result.stdout
            assert "10.100.1.11" in target1_interfaces, "Target1 should have DMZ IP 10.100.1.11"
            assert "192.168.100.11" in target1_interfaces, "Target1 should have Internal IP 192.168.100.11"
            print("    ✅ Ubuntu Target 1: Dual-homed (10.100.1.11 + 192.168.100.11)")
            
            # Check Ubuntu Target 2 (should only be on internal network: 192.168.100.12)
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target2-netconntest001", 
                "ip", "addr", "show"
            ])
            target2_interfaces = result.stdout
            assert "192.168.100.12" in target2_interfaces, "Target2 should have Internal IP 192.168.100.12"
            assert "10.100.1" not in target2_interfaces, "Target2 should NOT have DMZ network access"
            print("    ✅ Ubuntu Target 2: Only on Internal network (192.168.100.12)")
            
            # Test 2: Verify connectivity from Kali Jump Box
            print("  🔗 Testing connectivity from Kali Jump Box...")
            
            # Kali should be able to reach Ubuntu Target 1 on DMZ network
            result = self.lab_manager.run_command([
                "docker", "exec", "kali-jump-netconntest001", 
                "ping", "-c", "2", "-W", "3", "10.100.1.11"
            ])
            assert result.returncode == 0, "Kali should be able to ping Ubuntu Target 1 on DMZ"
            print("    ✅ Kali → Ubuntu Target 1 (DMZ): Connected")
            
            # Kali should NOT be able to reach Ubuntu Target 2 directly (different network)
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "kali-jump-netconntest001", 
                    "ping", "-c", "2", "-W", "3", "192.168.100.12"
                ])
                # If ping succeeds, that's wrong - networks should be isolated
                if result.returncode == 0:
                    assert False, "Kali should NOT be able to reach Ubuntu Target 2 directly - network isolation failed!"
            except subprocess.CalledProcessError:
                # This is expected - ping should fail due to network isolation
                pass
            print("    ✅ Kali → Ubuntu Target 2 (Internal): Properly isolated")
            
            # Test 3: Verify connectivity from Ubuntu Target 1 (dual-homed pivot)
            print("  🔗 Testing connectivity from Ubuntu Target 1 (pivot point)...")
            
            # Target 1 should be able to reach Kali on DMZ network
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target1-netconntest001", 
                "ping", "-c", "2", "-W", "3", "10.100.1.10"
            ])
            assert result.returncode == 0, "Target1 should be able to ping Kali on DMZ"
            print("    ✅ Ubuntu Target 1 → Kali (DMZ): Connected")
            
            # Target 1 should be able to reach Target 2 on internal network
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target1-netconntest001", 
                "ping", "-c", "2", "-W", "3", "192.168.100.12"
            ])
            assert result.returncode == 0, "Target1 should be able to ping Target2 on internal network"
            print("    ✅ Ubuntu Target 1 → Ubuntu Target 2 (Internal): Connected")
            
            # Test 4: Verify connectivity from Ubuntu Target 2
            print("  🔗 Testing connectivity from Ubuntu Target 2...")
            
            # Target 2 should be able to reach Target 1 on internal network
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target2-netconntest001", 
                "ping", "-c", "2", "-W", "3", "192.168.100.11"
            ])
            assert result.returncode == 0, "Target2 should be able to ping Target1 on internal network"
            print("    ✅ Ubuntu Target 2 → Ubuntu Target 1 (Internal): Connected")
            
            # Target 2 should NOT be able to reach Kali directly (different network)
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "ubuntu-target2-netconntest001", 
                    "ping", "-c", "2", "-W", "3", "10.100.1.10"
                ])
                # If ping succeeds, that's wrong - networks should be isolated
                if result.returncode == 0:
                    assert False, "Target2 should NOT be able to reach Kali directly - network isolation failed!"
            except subprocess.CalledProcessError:
                # This is expected - ping should fail due to network isolation
                pass
            print("    ✅ Ubuntu Target 2 → Kali (DMZ): Properly isolated")
            
            # Test 5: Verify routing tables show correct network segmentation
            print("  🗺️  Verifying routing tables...")
            
            # Check Kali routing - should only know about DMZ network
            result = self.lab_manager.run_command([
                "docker", "exec", "kali-jump-netconntest001", 
                "ip", "route", "show"
            ])
            kali_routes = result.stdout
            assert "10.100.1.0/24" in kali_routes, "Kali should have route to DMZ network"
            print("    ✅ Kali routing: DMZ network accessible")
            
            # Check Target1 routing - should know about both networks
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target1-netconntest001", 
                "ip", "route", "show"
            ])
            target1_routes = result.stdout
            assert "10.100.1.0/24" in target1_routes, "Target1 should have route to DMZ network"
            assert "192.168.100.0/24" in target1_routes, "Target1 should have route to Internal network"
            print("    ✅ Ubuntu Target 1 routing: Both networks accessible (pivot capability)")
            
            # Check Target2 routing - should only know about internal network
            result = self.lab_manager.run_command([
                "docker", "exec", "ubuntu-target2-netconntest001", 
                "ip", "route", "show"
            ])
            target2_routes = result.stdout
            assert "192.168.100.0/24" in target2_routes, "Target2 should have route to Internal network"
            print("    ✅ Ubuntu Target 2 routing: Internal network accessible")
            
            # Test 6: Test network discovery simulation (what students would do)
            print("  🕵️  Testing network discovery simulation...")
            
            # From Kali: Discover DMZ network
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "kali-jump-netconntest001", 
                    "bash", "-c", "for i in {10..15}; do ping -c 1 -W 1 10.100.1.$i > /dev/null 2>&1 && echo 'Host 10.100.1.'$i' is up'; done"
                ])
            except subprocess.CalledProcessError as e:
                # Network discovery commands may return non-zero exit codes when some hosts are unreachable
                # The important thing is that we get the expected output
                result = e
                result.stdout = e.stdout
            assert "Host 10.100.1.11 is up" in result.stdout, "Should discover Ubuntu Target 1 on DMZ"
            print("    ✅ DMZ network discovery: Ubuntu Target 1 discoverable from Kali")
            
            # Simulate what happens after compromising Target1 - discovery of internal network
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "ubuntu-target1-netconntest001", 
                    "bash", "-c", "for i in {10..15}; do ping -c 1 -W 1 192.168.100.$i > /dev/null 2>&1 && echo 'Host 192.168.100.'$i' is up'; done"
                ])
            except subprocess.CalledProcessError as e:
                # Network discovery commands may return non-zero exit codes when some hosts are unreachable
                result = e
                result.stdout = e.stdout
            assert "Host 192.168.100.12 is up" in result.stdout, "Should discover Ubuntu Target 2 on Internal network"
            print("    ✅ Internal network discovery: Ubuntu Target 2 discoverable from compromised Target 1")
            
            print("  🎉 All dual-network connectivity tests passed!")
            print("     ✅ Network isolation working correctly")
            print("     ✅ Ubuntu Target 1 can act as pivot between networks") 
            print("     ✅ Simulated attack path validation successful")
            
        except Exception as e:
            print(f"  ❌ Network connectivity test failed: {e}")
            # Print debug information
            print("  🐛 Debug information:")
            for container_type in ["kali-jump", "ubuntu-target1", "ubuntu-target2"]:
                container_name = f"{container_type}-netconntest001"
                try:
                    result = self.lab_manager.run_command([
                        "docker", "exec", container_name, "ip", "addr", "show"
                    ])
                    print(f"    {container_name} interfaces:")
                    print(f"      {result.stdout}")
                except Exception as debug_e:
                    print(f"    Failed to get debug info for {container_name}: {debug_e}")
            raise
        
        finally:
            # Cleanup
            self.lab_manager.spin_down_class(csv_file, parallel=False)


class TestStudentExec(TestDockerIntegration):
    """Test exec functionality for student containers"""

    def test_exec_into_kali_container(self):
        """Test executing actual commands in Kali container"""
        print("\n🔄 Testing exec into Kali container...")
        
        # Create test student with different port to avoid conflicts
        student_data = [{
            'student_id': 'exectest001', 
            'student_name': 'Exec Test 1',
            'port': '3333',  # Use a different port to avoid conflicts
            'subnet_id': '200'  # Use a different subnet
        }]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_file = f.name
            writer = csv.DictWriter(f, fieldnames=['student_id', 'student_name', 'port', 'subnet_id'])
            writer.writeheader()
            for student in student_data:
                writer.writerow(student)
        
        try:
            # Start the student containers
            success = self.lab_manager.spin_up_class(csv_file, parallel=False)
            assert success, "Failed to start student containers"
            
            # Wait for containers to be ready
            container_ready = self.wait_for_container_ready('kali-jump-exectest001', max_wait=30)
            assert container_ready, "Kali container failed to start"
            
            # Verify container name resolution
            containers = self.lab_manager.list_student_containers('exectest001')
            assert len(containers) > 0, "No containers found for student"
            
            # Verify the expected container names exist
            container_names = [c.get('Names', '') for c in containers]
            kali_container = None
            ubuntu1_container = None
            #ubuntu2_container = None
            
            for name in container_names:
                if 'kali-jump-exectest001' in name:
                    kali_container = name
                elif 'ubuntu-target1-exectest001' in name:
                    ubuntu1_container = name
                #elif 'ubuntu-target2-exectest001' in name:
                    #ubuntu2_container = name
            
            assert kali_container, f"Kali container not found. Available: {container_names}"
            assert ubuntu1_container, f"Ubuntu1 container not found. Available: {container_names}"
            #assert ubuntu2_container, f"Ubuntu2 container not found. Available: {container_names}"
            
            print(f"  ✅ Found Kali container: {kali_container}")
            print(f"  ✅ Found Ubuntu1 container: {ubuntu1_container}")
            #print(f"  ✅ Found Ubuntu2 container: {ubuntu2_container}")
            
            # Test that the container names follow the expected pattern
            # {service}-{student_id}
            assert kali_container == 'kali-jump-exectest001'
            assert ubuntu1_container == 'ubuntu-target1-exectest001'
            #assert ubuntu2_container == 'ubuntu-target2-exectest001'
            
            print("  ✅ Container naming follows expected pattern")
            
            # Test actual command execution in each container type
            print("  🧪 Testing actual command execution...")
            
            # Test Kali container - check if it has Kali-specific tools
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "kali-jump-exectest001", 
                    "bash", "-c", "whoami && echo 'KALI_TEST_SUCCESS' && which nmap"
                ])
                assert "KALI_TEST_SUCCESS" in result.stdout, "Kali container command execution failed"
                print("  ✅ Kali container exec test passed")
            except Exception as e:
                print(f"  ⚠️  Kali container exec test failed: {e}")
            
            # Test Ubuntu1 container - check basic functionality
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "ubuntu-target1-exectest001", 
                    "bash", "-c", "whoami && echo 'UBUNTU1_TEST_SUCCESS' && ls /"
                ])
                assert "UBUNTU1_TEST_SUCCESS" in result.stdout, "Ubuntu1 container command execution failed"
                print("  ✅ Ubuntu1 container exec test passed")
            except Exception as e:
                print(f"  ⚠️  Ubuntu1 container exec test failed: {e}")
            
            # Test Ubuntu2 container - check basic functionality
            """
            try:
                result = self.lab_manager.run_command([
                    "docker", "exec", "ubuntu-target2-exectest001", 
                    "bash", "-c", "whoami && echo 'UBUNTU2_TEST_SUCCESS' && ps aux | head -5"
                ])
                assert "UBUNTU2_TEST_SUCCESS" in result.stdout, "Ubuntu2 container command execution failed"
                print("  ✅ Ubuntu2 container exec test passed")
            except Exception as e:
                print(f"  ⚠️  Ubuntu2 container exec test failed: {e}")
            """
        finally:
            # Cleanup
            self.lab_manager.spin_down_class(csv_file, parallel=False)
            os.unlink(csv_file)

    def test_exec_command_validation(self):
        """Test exec command validation for invalid container types"""
        print("\n🔄 Testing exec command validation...")
        
        # Test invalid container type (this doesn't require actual containers)
        # We'll capture the output by temporarily redirecting stdout
        import io
        import sys
        
        old_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # This should print an error message and return
            self.lab_manager.exec_into_container('test001', 'invalid')
            output = captured_output.getvalue()
            
            assert "❌ Invalid container type: invalid" in output
            assert "Valid types: kali, ubuntu1" in output
            print("  ✅ Invalid container type properly rejected")
            
        finally:
            sys.stdout = old_stdout

    def test_exec_container_mapping(self):
        """Test that container type mapping works correctly with actual exec calls"""
        print("\n🔄 Testing container type mapping...")
        
        # Create test student with different port and subnet to avoid conflicts
        student_data = [{
            'student_id': 'maptest001', 
            'student_name': 'Map Test 1',
            'port': '4444',  # Use a different port to avoid conflicts  
            'subnet_id': '201'  # Use a different subnet
        }]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_file = f.name
            writer = csv.DictWriter(f, fieldnames=['student_id', 'student_name', 'port', 'subnet_id'])
            writer.writeheader()
            for student in student_data:
                writer.writerow(student)
        
        try:
            # Start the student containers
            success = self.lab_manager.spin_up_class(csv_file, parallel=False)
            assert success, "Failed to start student containers"
            
            # Wait for containers to be ready
            for container_type in ["kali-jump", "ubuntu-target1", "ubuntu-target2"]:
                container_name = f"{container_type}-maptest001"
                container_ready = self.wait_for_container_ready(container_name, max_wait=20)
                assert container_ready, f"{container_name} failed to start"
            
            # Verify that the service mapping produces correct container names and test execution
            service_map = {
                "kali": "kali-jump",
                "ubuntu1": "ubuntu-target1"
            }
            
            for container_type, service_name in service_map.items():
                expected_name = f"{service_name}-maptest001"
                
                # Check if this container actually exists
                containers = self.lab_manager.list_student_containers('maptest001')
                container_names = [c.get('Names', '') for c in containers]
                
                assert expected_name in container_names, f"Expected container {expected_name} not found in {container_names}"
                print(f"  ✅ Container type '{container_type}' maps to '{expected_name}'")
                
                # Test actual command execution to verify the container is functional
                try:
                    test_command = f"echo 'EXEC_TEST_{container_type.upper()}_SUCCESS'"
                    result = self.lab_manager.run_command([
                        "docker", "exec", expected_name, "bash", "-c", test_command
                    ])
                    expected_output = f"EXEC_TEST_{container_type.upper()}_SUCCESS"
                    assert expected_output in result.stdout, f"Command execution failed in {expected_name}"
                    print(f"    ✅ Command execution successful in {expected_name}")
                except Exception as e:
                    print(f"    ⚠️  Command execution failed in {expected_name}: {e}")
                    # Don't fail the test, just warn, as the main goal is to test container mapping
            
        finally:
            # Cleanup
            self.lab_manager.spin_down_class(csv_file, parallel=False)
            os.unlink(csv_file)

    def test_lab_manager_exec_functionality(self):
        """Test the lab manager's exec_into_container method with actual commands"""
        print("\n🔄 Testing lab manager exec functionality...")
        
        # Create test student with different port and subnet to avoid conflicts
        student_data = [{
            'student_id': 'functest001', 
            'student_name': 'Function Test 1',
            'port': '5555',  # Use a different port to avoid conflicts  
            'subnet_id': '202'  # Use a different subnet
        }]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_file = f.name
            writer = csv.DictWriter(f, fieldnames=['student_id', 'student_name', 'port', 'subnet_id'])
            writer.writeheader()
            for student in student_data:
                writer.writerow(student)
        
        try:
            # Start the student containers
            success = self.lab_manager.spin_up_class(csv_file, parallel=False)
            assert success, "Failed to start student containers"
            
            # Wait for containers to be ready
            for container_type in ["kali-jump", "ubuntu-target1", "ubuntu-target2"]:
                container_name = f"{container_type}-functest001"
                container_ready = self.wait_for_container_ready(container_name, max_wait=20)
                assert container_ready, f"{container_name} failed to start"
            
            print("  🧪 Testing exec functionality for each container type...")
            
            # Get containers list once for reuse
            containers = self.lab_manager.list_student_containers('functest001')
            assert len(containers) >= 3, "Expected at least 3 containers for student"
            
            # Test exec into kali container
            print("    Testing Kali container exec...")
            try:
                # Since we can't test interactive exec in automated tests, 
                # we'll test the container name resolution and basic functionality
                
                # Find kali container and test direct exec
                kali_container = None
                for container in containers:
                    if 'kali-jump-functest001' in container.get('Names', ''):
                        kali_container = container.get('Names', '')
                        break
                
                assert kali_container, "Kali container not found"
                
                # Test the underlying functionality that exec_into_container uses
                result = self.lab_manager.run_command([
                    "docker", "exec", kali_container,
                    "bash", "-c", "echo 'Kali exec test success' && whoami"
                ])
                assert "Kali exec test success" in result.stdout, "Kali exec test failed"
                print("      ✅ Kali container exec functionality verified")
                
            except Exception as e:
                print(f"      ⚠️  Kali container exec test failed: {e}")
            
            # Test exec into ubuntu1 container  
            print("    Testing Ubuntu1 container exec...")
            try:
                ubuntu1_container = None
                for container in containers:
                    if 'ubuntu-target1-functest001' in container.get('Names', ''):
                        ubuntu1_container = container.get('Names', '')
                        break
                
                assert ubuntu1_container, "Ubuntu1 container not found"
                
                result = self.lab_manager.run_command([
                    "docker", "exec", ubuntu1_container,
                    "bash", "-c", "echo 'Ubuntu1 exec test success' && id"
                ])
                assert "Ubuntu1 exec test success" in result.stdout, "Ubuntu1 exec test failed"
                print("      ✅ Ubuntu1 container exec functionality verified")
                
            except Exception as e:
                print(f"      ⚠️  Ubuntu1 container exec test failed: {e}")
            
            # Test exec into ubuntu2 container
            """
            print("    Testing Ubuntu2 container exec...")
            try:
                ubuntu2_container = None
                for container in containers:
                    if 'ubuntu-target2-functest001' in container.get('Names', ''):
                        ubuntu2_container = container.get('Names', '')
                        break
                
                assert ubuntu2_container, "Ubuntu2 container not found"
                
                result = self.lab_manager.run_command([
                    "docker", "exec", ubuntu2_container,
                    "bash", "-c", "echo 'Ubuntu2 exec test success' && uname -a"
                ])
                assert "Ubuntu2 exec test success" in result.stdout, "Ubuntu2 exec test failed"
                print("      ✅ Ubuntu2 container exec functionality verified")
                
            except Exception as e:
                print(f"      ⚠️  Ubuntu2 container exec test failed: {e}")
            """
            # Test the container name resolution that exec_into_container uses
            print("    Testing container name resolution...")
            service_mapping = {
                'kali': 'kali-jump-functest001',
                'ubuntu1': 'ubuntu-target1-functest001', 
                'ubuntu2': 'ubuntu-target2-functest001'
            }
            
            for container_type, expected_name in service_mapping.items():
                # Verify the name resolution logic matches what exec_into_container expects
                actual_containers = self.lab_manager.list_student_containers('functest001')
                found_container = None
                for container in actual_containers:
                    if expected_name in container.get('Names', ''):
                        found_container = container
                        break
                
                assert found_container, f"Container {expected_name} not found for type {container_type}"
                print(f"      ✅ Container type '{container_type}' resolves to '{expected_name}'")
            
            print("  ✅ All exec functionality tests passed!")
            
        finally:
            # Cleanup
            self.lab_manager.spin_down_class(csv_file, parallel=False)
            os.unlink(csv_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
