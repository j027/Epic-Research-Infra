#!/usr/bin/env python3
"""
Test suite for Lab Manager

This comprehensive test suite covers:
- CSV operations (read/write)
- Port assignment and collision detection
- Subnet assignment and collision detection
- Assignment service functionality
- Integration scenarios with duplicate handling
- Edge cases and error conditions

Run with: python -m pytest test_lab_manager.py -v
"""

import pytest
import tempfile
import os
import csv
import json
from unittest.mock import Mock, patch, MagicMock
from typing import List, Set

# Import the classes and functions we want to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lab_manager import LabManager, StudentData


class TestLabManager:
    """Test the core LabManager functionality"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.lab_manager = LabManager(use_sudo=False)  # Don't use sudo in tests
        
    def create_test_csv(self, students_data: List[dict]) -> str:
        """Helper to create a temporary CSV file with test data"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        # Write CSV data
        fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students_data:
            writer.writerow(student)
        
        temp_file.close()
        return temp_file.name
    
    def teardown_method(self):
        """Clean up after each test method"""
        # Clean up any temporary files created during tests
        pass


class TestPortAssignment:
    """Test port assignment functionality"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def test_auto_assign_port_empty_set(self):
        """Test port assignment with no existing ports"""
        result = self.lab_manager.auto_assign_port(set())
        assert result == 2222
    
    def test_auto_assign_port_with_existing(self):
        """Test port assignment with existing ports"""
        existing_ports = {2222, 2223, 2225}
        result = self.lab_manager.auto_assign_port(existing_ports)
        assert result == 2224  # First available port
    
    def test_auto_assign_port_sequential(self):
        """Test multiple sequential port assignments"""
        used_ports = set()
        
        # Assign 5 ports sequentially
        for i in range(5):
            port = self.lab_manager.auto_assign_port(used_ports)
            assert port == 2222 + i
            used_ports.add(port)
    
    def test_auto_assign_port_with_gaps(self):
        """Test port assignment with gaps in sequence"""
        existing_ports = {2222, 2224, 2226}  # Gaps at 2223, 2225
        result = self.lab_manager.auto_assign_port(existing_ports)
        assert result == 2223  # Should fill first gap


class TestSubnetAssignment:
    """Test subnet assignment functionality"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def test_calculate_subnet_id_deterministic(self):
        """Test that subnet calculation is deterministic for same student ID"""
        student_id = "student001"
        used_subnets = set()
        
        result1 = self.lab_manager.calculate_subnet_id(student_id, used_subnets)
        result2 = self.lab_manager.calculate_subnet_id(student_id, used_subnets)
        
        assert result1 == result2
        assert 1 <= result1 <= 254
    
    def test_calculate_subnet_id_collision_avoidance(self):
        """Test subnet collision avoidance"""
        student_id = "student001"
        used_subnets = set()
        
        # Get the natural subnet for this student
        natural_subnet = self.lab_manager.calculate_subnet_id(student_id, used_subnets)
        
        # Mark it as used and try again
        used_subnets.add(natural_subnet)
        collision_avoided_subnet = self.lab_manager.calculate_subnet_id(student_id, used_subnets)
        
        assert collision_avoided_subnet != natural_subnet
        assert collision_avoided_subnet not in used_subnets
        assert 1 <= collision_avoided_subnet <= 254
    
    def test_calculate_subnet_id_different_students(self):
        """Test that different students get different subnets (usually)"""
        used_subnets = set()
        
        subnet1 = self.lab_manager.calculate_subnet_id("student001", used_subnets)
        used_subnets.add(subnet1)
        
        subnet2 = self.lab_manager.calculate_subnet_id("student002", used_subnets)
        
        # They should be different (with very high probability)
        assert subnet1 != subnet2


class TestCSVOperations:
    """Test CSV reading and writing operations"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def create_test_csv(self, students_data: List[dict]) -> str:
        """Helper to create a temporary CSV file with test data"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students_data:
            writer.writerow(student)
        
        temp_file.close()
        return temp_file.name
    
    def test_read_empty_csv(self):
        """Test reading an empty CSV file"""
        csv_file = self.create_test_csv([])
        
        try:
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=False)
            assert students == []
        finally:
            os.unlink(csv_file)
    
    def test_read_csv_with_complete_data(self):
        """Test reading CSV with complete port and subnet data"""
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': '2222', 'subnet_id': '10'},
            {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': '2223', 'subnet_id': '20'}
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=False)
            
            assert len(students) == 2
            assert students[0]['student_id'] == 'student001'
            assert students[0]['port'] == 2222
            assert students[0]['subnet_id'] == 10
            assert students[1]['student_id'] == 'student002'
            assert students[1]['port'] == 2223
            assert students[1]['subnet_id'] == 20
        finally:
            os.unlink(csv_file)
    
    def test_read_csv_with_missing_assignments(self):
        """Test reading CSV with missing port/subnet assignments"""
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': '', 'subnet_id': ''},
            {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': '2223', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=False)
            
            assert len(students) == 2
            assert students[0]['port'] == 0  # Should default to 0 for missing port
            assert students[0]['subnet_id'] is None  # Should default to None for missing subnet
            assert students[1]['port'] == 2223  # Should preserve existing port
            assert students[1]['subnet_id'] is None  # Should default to None for missing subnet
        finally:
            os.unlink(csv_file)
    
    def test_get_used_ports_from_csv(self):
        """Test extracting used ports from CSV"""
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice', 'port': '2222', 'subnet_id': '10'},
            {'student_id': 'student002', 'student_name': 'Bob', 'port': '2225', 'subnet_id': '20'},
            {'student_id': 'student003', 'student_name': 'Carol', 'port': '', 'subnet_id': '30'}  # Empty port
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            used_ports = self.lab_manager.get_used_ports(csv_file)
            assert used_ports == {2222, 2225}  # Should only include valid ports
        finally:
            os.unlink(csv_file)
    
    def test_get_used_subnets_from_csv(self):
        """Test extracting used subnets from CSV"""
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice', 'port': '2222', 'subnet_id': '10'},
            {'student_id': 'student002', 'student_name': 'Bob', 'port': '2225', 'subnet_id': '25'},
            {'student_id': 'student003', 'student_name': 'Carol', 'port': '2226', 'subnet_id': ''}  # Empty subnet
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            used_subnets = self.lab_manager.get_used_subnets(csv_file)
            assert used_subnets == {10, 25}  # Should only include valid subnets
        finally:
            os.unlink(csv_file)


class TestEnsureAssignments:
    """Test the centralized assignment service"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def create_test_csv(self, students_data: List[dict]) -> str:
        """Helper to create a temporary CSV file with test data"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students_data:
            writer.writerow(student)
        
        temp_file.close()
        return temp_file.name
    
    def test_ensure_assignments_empty_list(self):
        """Test ensure_assignments with empty student list"""
        csv_file = self.create_test_csv([])
        
        try:
            result = self.lab_manager.ensure_assignments([], csv_file)
            assert result == []
        finally:
            os.unlink(csv_file)
    
    def test_ensure_assignments_complete_data(self):
        """Test ensure_assignments with students that already have assignments"""
        # Create CSV with existing assignments
        csv_data = [
            {'student_id': 'student001', 'student_name': 'Alice', 'port': '2222', 'subnet_id': '10'}
        ]
        csv_file = self.create_test_csv(csv_data)
        
        try:
            students: List[StudentData] = [
                {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': 2222, 'subnet_id': 10}
            ]
            
            result = self.lab_manager.ensure_assignments(students, csv_file)
            
            # Should return unchanged since assignments are already valid
            assert len(result) == 1
            assert result[0]['port'] == 2222
            assert result[0]['subnet_id'] == 10
        finally:
            os.unlink(csv_file)
    
    def test_ensure_assignments_missing_ports(self):
        """Test ensure_assignments assigns ports to students without them"""
        csv_file = self.create_test_csv([])  # Empty CSV
        
        try:
            students: List[StudentData] = [
                {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': 0, 'subnet_id': None},
                {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': 0, 'subnet_id': None}
            ]
            
            result = self.lab_manager.ensure_assignments(students, csv_file)
            
            assert len(result) == 2
            assert result[0]['port'] == 2222  # First student gets 2222
            assert result[1]['port'] == 2223  # Second student gets 2223
            assert result[0]['subnet_id'] is not None
            assert result[1]['subnet_id'] is not None
            assert result[0]['subnet_id'] != result[1]['subnet_id']  # Different subnets
        finally:
            os.unlink(csv_file)
    
    def test_ensure_assignments_port_collision(self):
        """Test ensure_assignments handles port collisions correctly"""
        # Create CSV with existing port assignment
        csv_data = [
            {'student_id': 'existing_student', 'student_name': 'Existing', 'port': '2222', 'subnet_id': '10'}
        ]
        csv_file = self.create_test_csv(csv_data)
        
        try:
            # Try to assign a student with conflicting port
            students: List[StudentData] = [
                {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': 2222, 'subnet_id': None}
            ]
            
            result = self.lab_manager.ensure_assignments(students, csv_file)
            
            assert len(result) == 1
            assert result[0]['port'] != 2222  # Should get reassigned to avoid collision
            assert result[0]['port'] >= 2223  # Should get next available port
        finally:
            os.unlink(csv_file)
    
    def test_ensure_assignments_subnet_collision(self):
        """Test ensure_assignments handles subnet collisions correctly"""
        # Create CSV with existing subnet assignment
        csv_data = [
            {'student_id': 'existing_student', 'student_name': 'Existing', 'port': '2222', 'subnet_id': '42'}
        ]
        csv_file = self.create_test_csv(csv_data)
        
        try:
            # Try to assign a student with conflicting subnet
            students: List[StudentData] = [
                {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': 0, 'subnet_id': 42}
            ]
            
            result = self.lab_manager.ensure_assignments(students, csv_file)
            
            assert len(result) == 1
            assert result[0]['subnet_id'] != 42  # Should get reassigned to avoid collision
            assert result[0]['subnet_id'] is not None
            assert 1 <= result[0]['subnet_id'] <= 254  # Should be in valid range
        finally:
            os.unlink(csv_file)


class TestIntegrationScenarios:
    """Test complete integration scenarios"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def create_test_csv(self, students_data: List[dict]) -> str:
        """Helper to create a temporary CSV file with test data"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students_data:
            writer.writerow(student)
        
        temp_file.close()
        return temp_file.name
    
    def test_full_csv_processing_with_mixed_data(self):
        """Test complete CSV processing with mix of complete and incomplete data"""
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': '2222', 'subnet_id': '10'},
            {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': '', 'subnet_id': ''},
            {'student_id': 'student003', 'student_name': 'Carol Brown', 'port': '2225', 'subnet_id': ''},
            {'student_id': 'student004', 'student_name': 'Dave Wilson', 'port': '', 'subnet_id': '30'}
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            # Read and process the CSV
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=True)
            
            assert len(students) == 4
            
            # Check that all students have valid assignments
            assigned_ports = set()
            assigned_subnets = set()
            
            for student in students:
                assert student['port'] >= 2222
                assert student['subnet_id'] is not None
                assert 1 <= student['subnet_id'] <= 254
                
                # Check for duplicates
                assert student['port'] not in assigned_ports
                assert student['subnet_id'] not in assigned_subnets
                
                assigned_ports.add(student['port'])
                assigned_subnets.add(student['subnet_id'])
            
            # Verify specific expected values
            alice = next(s for s in students if s['student_id'] == 'student001')
            assert alice['port'] == 2222  # Should keep existing port
            assert alice['subnet_id'] == 10  # Should keep existing subnet
            
            carol = next(s for s in students if s['student_id'] == 'student003')
            assert carol['port'] == 2225  # Should keep existing port
            
        finally:
            os.unlink(csv_file)
    
    def test_duplicate_port_handling_in_csv(self):
        """Test handling of duplicate ports in CSV data"""
        # Create CSV with duplicate ports (invalid scenario)
        test_data = [
            {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': '2222', 'subnet_id': '10'},
            {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': '2222', 'subnet_id': '20'},  # Duplicate!
            {'student_id': 'student003', 'student_name': 'Carol Brown', 'port': '', 'subnet_id': ''}
        ]
        csv_file = self.create_test_csv(test_data)
        
        try:
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=True)
            
            assert len(students) == 3
            
            # Check that all ports are unique after processing
            ports = [s['port'] for s in students]
            assert len(ports) == len(set(ports))  # No duplicates
            
            # Bob should have been reassigned
            bob = next(s for s in students if s['student_id'] == 'student002')
            assert bob['port'] != 2222
            
        finally:
            os.unlink(csv_file)
    
    def test_large_class_assignment(self):
        """Test assignment for a larger class to check for performance and correctness"""
        # Create a larger dataset
        test_data = []
        for i in range(1, 51):  # 50 students
            test_data.append({
                'student_id': f'student{i:03d}',
                'student_name': f'Student {i}',
                'port': '',  # All need port assignment
                'subnet_id': ''  # All need subnet assignment
            })
        
        csv_file = self.create_test_csv(test_data)
        
        try:
            students = self.lab_manager.read_students_csv(csv_file, update_if_changed=True)
            
            assert len(students) == 50
            
            # Check all assignments are unique
            ports = [s['port'] for s in students]
            subnets = [s['subnet_id'] for s in students]
            
            assert len(set(ports)) == 50  # All ports unique
            assert len(set(subnets)) == 50  # All subnets unique
            
            # Check port range
            assert min(ports) == 2222
            assert max(ports) == 2222 + 49  # Sequential assignment
            
            # Check subnet range
            for subnet in subnets:
                assert subnet is not None
                assert 1 <= subnet <= 254
                
        finally:
            os.unlink(csv_file)


class TestEnvironmentGeneration:
    """Test environment variable generation"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def test_get_student_env_complete(self):
        """Test environment generation with complete data"""
        env = self.lab_manager.get_student_env(
            student_id="student001",
            student_name="Alice Smith",
            port=2222,
            subnet_id=42
        )
        
        expected = {
            'STUDENT_ID': 'student001',
            'STUDENT_NAME': 'Alice Smith',
            'SSH_PORT': '2222',
            'SUBNET_ID': '42',
            'NETWORK_NAME': 'cyber-lab-student001'
        }
        
        assert env == expected
    
    def test_get_student_env_with_subnet_calculation(self):
        """Test environment generation with subnet calculation"""
        # Create a temporary CSV for subnet calculation
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        temp_file.close()
        
        try:
            env = self.lab_manager.get_student_env(
                student_id="student001",
                student_name="Alice Smith",
                port=2222,
                subnet_id=None,  # Will be calculated
                csv_file=temp_file.name
            )
            
            assert env['STUDENT_ID'] == 'student001'
            assert env['STUDENT_NAME'] == 'Alice Smith'
            assert env['SSH_PORT'] == '2222'
            assert 'SUBNET_ID' in env
            assert env['NETWORK_NAME'] == 'cyber-lab-student001'
            
            # Subnet should be calculated and valid
            subnet_id = int(env['SUBNET_ID'])
            assert 1 <= subnet_id <= 254
            
        finally:
            os.unlink(temp_file.name)


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def setup_method(self):
        self.lab_manager = LabManager(use_sudo=False)
    
    def test_read_nonexistent_csv(self):
        """Test reading a CSV file that doesn't exist"""
        nonexistent_file = "/tmp/definitely_does_not_exist.csv"
        
        students = self.lab_manager.read_students_csv(nonexistent_file, update_if_changed=False)
        assert students == []
    
    def test_get_used_ports_nonexistent_csv(self):
        """Test getting used ports from nonexistent CSV"""
        nonexistent_file = "/tmp/definitely_does_not_exist.csv"
        
        used_ports = self.lab_manager.get_used_ports(nonexistent_file)
        assert used_ports == set()
    
    def test_get_used_subnets_nonexistent_csv(self):
        """Test getting used subnets from nonexistent CSV"""
        nonexistent_file = "/tmp/definitely_does_not_exist.csv"
        
        used_subnets = self.lab_manager.get_used_subnets(nonexistent_file)
        assert used_subnets == set()


# Test runner configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
