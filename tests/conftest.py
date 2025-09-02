"""
Shared test fixtures and configuration for lab_manager tests
"""

import pytest
import tempfile
import os
import csv
from typing import List


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing"""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
    temp_file.close()
    yield temp_file.name
    # Cleanup
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass


@pytest.fixture
def sample_students_data():
    """Sample student data for testing"""
    return [
        {'student_id': 'student001', 'student_name': 'Alice Smith', 'port': '2222', 'subnet_id': '10'},
        {'student_id': 'student002', 'student_name': 'Bob Jones', 'port': '2223', 'subnet_id': '20'},
        {'student_id': 'student003', 'student_name': 'Carol Brown', 'port': '', 'subnet_id': ''}
    ]


def create_csv_with_data(csv_file: str, students_data: List[dict]) -> None:
    """Helper function to create a CSV file with test data"""
    fieldnames = ['student_id', 'student_name', 'port', 'subnet_id']
    
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for student in students_data:
            writer.writerow(student)
