#!/usr/bin/env python3
"""
Test suite for Flag System Integration

Tests the flag system by actually building and running containers
to verify that flags are created correctly with custom passwords.

Run with: python -m pytest test_flag_system.py -v
"""

import pytest
import subprocess
import os
import time
import tempfile


class TestFlagContainerIntegration:
    """Integration tests that build actual containers and verify flag functionality"""
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.test_flag_content = "flag{integration_test_flag_123}"
        self.test_password = "test_password_456"
        self.test_location = "/var/log/flag.zip"
        
    def run_command(self, command, check=True, **kwargs):
        """Helper to run shell commands with consistent error handling"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, **kwargs)
            if check and result.returncode != 0:
                print(f"Command failed: {command}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                result.check_returncode()
            return result
        except subprocess.CalledProcessError as e:
            print(f"Command failed with exit code {e.returncode}: {command}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            raise
            
    def test_flag_creation_in_container(self):
        """Test that a container can be started with custom flag and password, and the flag can be extracted"""
        
        print("\n🏗️  Building base ubuntu-target1 container...")
        
        # Get the project root directory relative to this test file
        project_root = os.path.dirname(os.path.dirname(__file__))
        ubuntu_target1_dir = os.path.join(project_root, "ubuntu-target1")
        
        # Build the standard ubuntu-target1 image
        build_command = f"cd {ubuntu_target1_dir} && sudo docker build -t test-flag-container ."
        build_result = self.run_command(build_command)
        
        try:
            print("🚀 Starting container with custom environment variables...")
            
            # Start container with custom environment variables
            start_command = f"""sudo docker run -d --name test-flag-running \\
                -e FLAG_CONTENT='{self.test_flag_content}' \\
                -e ZIP_PASSWORD='{self.test_password}' \\
                -e FLAG_LOCATION='{self.test_location}' \\
                test-flag-container"""
            
            self.run_command(start_command)
            
            # Wait for container to start and flag creation to complete
            import time
            time.sleep(3)
            
            print("🔍 Checking if flag file was created...")
            
            # Check if flag file exists
            check_file_command = f"sudo docker exec test-flag-running ls -la {self.test_location}"
            file_result = self.run_command(check_file_command)
            
            # Verify the flag file exists
            assert "flag.zip" in file_result.stdout, f"Flag file not found at {self.test_location}"
            
            print("🔓 Testing flag extraction with correct password...")
            
            # Extract and verify flag content (suppress unzip output)
            extract_command = f"""sudo docker exec test-flag-running bash -c "unzip -q -P '{self.test_password}' {self.test_location} -d /tmp/test_extract && cat /tmp/test_extract/tmp/flag.txt" """
            
            extract_result = self.run_command(extract_command)
            
            # Verify the extracted flag content matches what we set
            extracted_flag = extract_result.stdout.strip()
            assert extracted_flag == self.test_flag_content, f"Expected '{self.test_flag_content}', got '{extracted_flag}'"
            
            print("🔒 Verifying create-flag.sh script was deleted...")
            
            # Verify the script deleted itself for security
            script_check = self.run_command("sudo docker exec test-flag-running ls -la /create-flag.sh", check=False)
            assert script_check.returncode != 0, "create-flag.sh should be deleted after execution"
            
            print("✅ Flag creation and extraction test passed!")
            
        finally:
            # Cleanup: Remove running container and image
            self.run_command("sudo docker rm -f test-flag-running", check=False)
            self.run_command("sudo docker rmi test-flag-container", check=False)
            
    def test_flag_with_wrong_password_fails(self):
        """Test that using the wrong password fails to extract the flag"""
        
        print("\n🏗️  Testing wrong password rejection...")
        
        # Get the project root directory relative to this test file
        project_root = os.path.dirname(os.path.dirname(__file__))
        ubuntu_target1_dir = os.path.join(project_root, "ubuntu-target1")
        
        # Build the standard image
        build_command = f"cd {ubuntu_target1_dir} && sudo docker build -t test-flag-wrong-password ."
        build_result = self.run_command(build_command)
        
        try:
            # Start container with correct credentials
            start_command = f"""sudo docker run -d --name test-flag-wrong-pwd \\
                -e FLAG_CONTENT='{self.test_flag_content}' \\
                -e ZIP_PASSWORD='{self.test_password}' \\
                -e FLAG_LOCATION='{self.test_location}' \\
                test-flag-wrong-password"""
            
            self.run_command(start_command)
            
            # Wait for flag creation
            import time
            time.sleep(3)
            
            print("🔒 Testing extraction with wrong password...")
            
            # Try to extract with wrong password - this should fail
            wrong_password = "definitely_wrong_password"
            extract_command = f"""sudo docker exec test-flag-wrong-pwd bash -c "unzip -P '{wrong_password}' {self.test_location} -d /tmp/test_extract" """
            
            # This should fail (non-zero exit code)
            extract_result = self.run_command(extract_command, check=False)
            
            # Verify that extraction failed due to incorrect password
            assert extract_result.returncode != 0, "Expected extraction to fail with wrong password"
            assert "incorrect password" in extract_result.stderr.lower() or "skipping" in extract_result.stdout.lower()
            
            print("✅ Wrong password correctly rejected!")
            
        finally:
            # Cleanup
            self.run_command("sudo docker rm -f test-flag-wrong-pwd", check=False)
            self.run_command("sudo docker rmi test-flag-wrong-password", check=False)
            
    def test_flag_with_environment_variables(self):
        """Test flag creation using environment variables (runtime approach)"""
        
        print("\n🌍 Testing flag creation with environment variables...")
        
        # Get the project root directory relative to this test file
        project_root = os.path.dirname(os.path.dirname(__file__))
        ubuntu_target1_dir = os.path.join(project_root, "ubuntu-target1")
        
        # Build the base image first
        build_command = f"cd {ubuntu_target1_dir} && sudo docker build -t test-flag-env-base ."
        build_result = self.run_command(build_command)
        
        try:
            # Run container with environment variables set
            run_command = f"""
            sudo docker run --rm \\
                -e FLAG_CONTENT='{self.test_flag_content}' \\
                -e ZIP_PASSWORD='{self.test_password}' \\
                -e FLAG_LOCATION='{self.test_location}' \\
                --entrypoint '' \\
                test-flag-env-base \\
                bash -c "/create-flag.sh && unzip -P '{self.test_password}' {self.test_location} -d /tmp/extract && cat /tmp/extract/tmp/flag.txt"
            """
            
            result = self.run_command(run_command)
            
            # Verify the flag content
            extracted_flag = result.stdout.strip().split('\n')[-1]  # Get last line (the flag)
            assert extracted_flag == self.test_flag_content, f"Expected '{self.test_flag_content}', got '{extracted_flag}'"
            
            print("✅ Environment variable flag creation test passed!")
            
        finally:
            # Cleanup
            cleanup_command = "sudo docker rmi test-flag-env-base"
            self.run_command(cleanup_command, check=False)


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])