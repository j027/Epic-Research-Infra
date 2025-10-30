#!/usr/bin/env python3
"""
Test suite for Flag System Integration

Tests that flags are created correctly at runtime with custom passwords.

Run with: python -m pytest tests/test_flag_system.py -v
"""

import pytest
import subprocess
import time


class TestFlagSystem:
    """Test flag creation at container runtime"""
    
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
    
    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.test_flag_content = "flag{test_flag_runtime}"
        self.test_password = "testpass123"
        self.test_location = "/var/log/test_flag.zip"
        self.image_name = "epic-research-infra-ubuntu-target1:latest"
        
        # Auto-detect if sudo is needed for Docker
        self.use_sudo = self._needs_sudo_for_docker()
        print(f"\n🔧 Using sudo for Docker: {self.use_sudo}")
        
    def run_command(self, command, check=True, **kwargs):
        """Helper to run shell commands"""
        # Prepend sudo if needed
        if self.use_sudo and command.strip().startswith("docker"):
            command = f"sudo {command}"
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True, **kwargs)
        if check and result.returncode != 0:
            print(f"Command failed: {command}")
            print(f"STDERR: {result.stderr}")
        return result
    
    @pytest.mark.integration
    def test_flag_creation_runtime(self):
        """Test that flags are created correctly at runtime with custom env vars"""
        
        print(f"\n🧪 Testing runtime flag creation with image: {self.image_name}")
        
        container_name = "test-flag-runtime"
        
        try:
            print("🚀 Starting container with custom flag environment variables...")
            
            # Start container with custom environment variables
            start_command = f"""docker run -d --name {container_name} \
                -e FLAG_CONTENT='{self.test_flag_content}' \
                -e ZIP_PASSWORD='{self.test_password}' \
                -e FLAG_LOCATION='{self.test_location}' \
                {self.image_name}"""
            
            result = self.run_command(start_command)
            assert result.returncode == 0, f"Failed to start container: {result.stderr}"
            
            # Wait for container startup and flag creation
            time.sleep(5)
            
            print("🔍 Verifying flag file was created...")
            
            # Check if flag file exists
            check_result = self.run_command(
                f"docker exec {container_name} test -f {self.test_location} && echo 'exists'"
            )
            assert "exists" in check_result.stdout, f"Flag file not found at {self.test_location}"
            
            print("🔓 Extracting and verifying flag content...")
            
            # Extract flag and read content
            extract_command = f"""docker exec {container_name} bash -c \
                "unzip -q -P '{self.test_password}' {self.test_location} -d /tmp/extract && \
                cat /tmp/extract/flag.txt" """
            
            extract_result = self.run_command(extract_command)
            assert extract_result.returncode == 0, f"Failed to extract flag: {extract_result.stderr}"
            
            # Verify flag content
            extracted_flag = extract_result.stdout.strip()
            assert extracted_flag == self.test_flag_content, \
                f"Expected '{self.test_flag_content}', got '{extracted_flag}'"
            
            print("✅ Flag creation and extraction successful!")
            
        finally:
            # Cleanup
            self.run_command(f"docker rm -f {container_name}", check=False)


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])