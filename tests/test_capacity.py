#!/usr/bin/env python3
"""
Capacity Testing Script for Cybersecurity Lab Environment

Uses binary search to find the maximum number of students your system can handle.
This test is designed for MANUAL execution only - not for CI/CD.

Run with: python -m pytest tests/test_capacity.py -v -s -m capacity

The test will:
1. Start with a known working configuration (min_students)
2. Test progressively larger student counts using binary search
3. Stop when it finds the breaking point
4. Report the maximum capacity

Success criteria (WORST CASE):
- ALL students must complete successfully (100% success rate)
- Total test time stays under threshold (15 minutes)
- No timeouts (our timeouts are already generous)
- Performance must stay within 150% of single-student baseline
  (i.e., if 1 student takes 100s, N students can average up to 150s each)
"""

import pytest
import subprocess
import os
import sys
import time
import tempfile
import csv
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from test_load to reuse StudentSimulator
from tests.test_load import StudentSimulator


class CapacityTestConfig:
    """Configuration for capacity testing"""
    
    def __init__(self):
        # Binary search bounds
        self.min_students = 1  # Known working minimum
        self.max_students = 100  # Theoretical maximum to test
        
        # Success criteria - WORST CASE SCENARIO
        # All students must complete successfully - no failures tolerated
        self.min_success_rate = 1.0  # 100% students must succeed (worst case)
        self.max_duration = 900  # 15 minutes max per test (generous but failure if exceeded)
        
        # Performance thresholds - RELATIVE TO BASELINE
        # First we measure single-student performance to establish baseline
        # Then we allow degradation up to this multiplier
        self.baseline_duration = None  # Will be set after single-student test
        self.acceptable_degradation_multiplier = 1.5  # 150% of baseline (50% slower is acceptable)
        
        # Timeouts are treated as hard failures since our timeouts are already generous
        self.treat_timeouts_as_failures = True
        
        # Binary search settings
        self.max_iterations = 10  # Limit search iterations


class CapacityTester:
    """Handles capacity testing with binary search"""
    
    def __init__(self, lab_manager):
        self.lab_manager = lab_manager
        self.config = CapacityTestConfig()
        self.test_results: List[Dict] = []
        self.max_working_capacity = 0
        self.baseline_measured = False
        
    def test_capacity(self, num_students: int) -> Tuple[bool, Dict]:
        """
        Test if system can handle num_students concurrently.
        Returns (success, metrics_dict)
        """
        print(f"\n{'='*80}")
        print(f"🧪 Testing capacity with {num_students} students")
        print(f"{'='*80}")
        
        # Create test CSV
        csv_path = self._create_test_csv(num_students)
        
        # Override confirmation to auto-accept
        original_confirm = self.lab_manager._confirm_parallel_execution
        self.lab_manager._confirm_parallel_execution = lambda operation_name: True
        
        start_time = time.time()
        
        try:
            # Provision student environments
            print(f"📚 Provisioning {num_students} student environments...")
            provision_start = time.time()
            
            success = self.lab_manager.spin_up_class(csv_path, parallel=True)
            provision_duration = time.time() - provision_start
            
            if not success:
                print(f"❌ Failed to provision students")
                return False, {
                    'num_students': num_students,
                    'provision_duration': provision_duration,
                    'total_duration': time.time() - start_time,
                    'success': False,
                    'failure_reason': 'provision_failed'
                }
            
            print(f"✅ Provisioned in {provision_duration:.1f}s")
            
            # Read assigned ports
            students = self._read_student_assignments(csv_path)
            if len(students) != num_students:
                print(f"❌ Not all students were assigned ports")
                return False, {
                    'num_students': num_students,
                    'provision_duration': provision_duration,
                    'total_duration': time.time() - start_time,
                    'success': False,
                    'failure_reason': 'port_assignment_failed'
                }
            
            # Run simulations
            print(f"🎭 Running {num_students} concurrent student simulations...")
            sim_start = time.time()
            
            results = []
            with ThreadPoolExecutor(max_workers=num_students) as executor:
                futures = []
                
                for student_data in students:
                    simulator = StudentSimulator(
                        student_data['student_id'],
                        student_data['student_name'],
                        "localhost",
                        int(student_data['port'])
                    )
                    future = executor.submit(simulator.run_full_simulation)
                    futures.append(future)
                
                # Collect results with timeout
                for future in as_completed(futures, timeout=self.config.max_duration):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"❌ Simulation failed: {e}")
                        results.append({
                            'student_id': 'unknown',
                            'overall_success': False,
                            'error': str(e),
                            'total_duration': 0
                        })
            
            sim_duration = time.time() - sim_start
            total_duration = time.time() - start_time
            
            # Analyze results
            metrics = self._analyze_capacity_results(
                num_students, results, provision_duration, sim_duration, total_duration
            )
            
            # Determine success based on criteria
            success = self._evaluate_success(metrics)
            
            return success, metrics
            
        except Exception as e:
            print(f"❌ Capacity test failed with exception: {e}")
            return False, {
                'num_students': num_students,
                'total_duration': time.time() - start_time,
                'success': False,
                'failure_reason': f'exception: {str(e)}'
            }
        finally:
            # Cleanup
            try:
                print(f"🧹 Cleaning up {num_students} student environments...")
                self.lab_manager.spin_down_class(csv_path, parallel=True)
            except Exception as e:
                print(f"⚠️  Cleanup failed: {e}")
            finally:
                self.lab_manager._confirm_parallel_execution = original_confirm
                if os.path.exists(csv_path):
                    os.unlink(csv_path)
    
    def _analyze_capacity_results(self, num_students: int, results: List[Dict],
                                  provision_duration: float, sim_duration: float,
                                  total_duration: float) -> Dict:
        """Analyze test results and return metrics"""
        
        successful = sum(1 for r in results if r.get('overall_success', False))
        failed = len(results) - successful
        success_rate = successful / len(results) if results else 0
        
        # Calculate average durations
        durations = [r.get('total_duration', 0) for r in results if r.get('total_duration', 0) > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        metrics = {
            'num_students': num_students,
            'total_containers': num_students * 3,  # 3 containers per student
            'provision_duration': provision_duration,
            'simulation_duration': sim_duration,
            'total_duration': total_duration,
            'successful_students': successful,
            'failed_students': failed,
            'success_rate': success_rate,
            'avg_student_duration': avg_duration,
            'max_student_duration': max_duration,
            'students_per_second': num_students / total_duration if total_duration > 0 else 0,
        }
        
        return metrics
    
    def _evaluate_success(self, metrics: Dict) -> bool:
        """
        Evaluate if the test was successful based on WORST CASE criteria.
        
        Requirements:
        - 100% success rate (all students must complete)
        - No timeouts (our timeouts are already generous)
        - Total duration under max threshold
        - Performance must be within acceptable degradation of baseline
        """
        
        # Check success rate - MUST be 100% (worst case: all students succeed)
        if metrics['success_rate'] < self.config.min_success_rate:
            print(f"❌ Success rate requirement not met: {metrics['success_rate']:.1%} < {self.config.min_success_rate:.1%}")
            print(f"   Worst case scenario requires ALL students to succeed")
            print(f"   {metrics['failed_students']}/{metrics['num_students']} students failed")
            return False
        
        # Check total duration - generous but still a limit
        if metrics['total_duration'] > self.config.max_duration:
            print(f"❌ Test exceeded maximum duration: {metrics['total_duration']:.1f}s > {self.config.max_duration}s")
            print(f"   Even with generous timeouts, system took too long")
            return False
        
        # Check performance degradation against baseline (if baseline is set)
        if self.config.baseline_duration is not None:
            max_acceptable_duration = self.config.baseline_duration * self.config.acceptable_degradation_multiplier
            
            if metrics['avg_student_duration'] > max_acceptable_duration:
                print(f"❌ Performance degradation exceeded acceptable limit:")
                print(f"   Baseline (1 student): {self.config.baseline_duration:.1f}s")
                print(f"   Current avg: {metrics['avg_student_duration']:.1f}s")
                print(f"   Max acceptable ({self.config.acceptable_degradation_multiplier:.0%} of baseline): {max_acceptable_duration:.1f}s")
                print(f"   Degradation: {(metrics['avg_student_duration'] / self.config.baseline_duration):.1%} of baseline")
                return False
            elif metrics['avg_student_duration'] > self.config.baseline_duration:
                # Performance degraded but within acceptable range
                degradation_pct = (metrics['avg_student_duration'] / self.config.baseline_duration) * 100
                print(f"⚠️  Performance degraded but within acceptable limits:")
                print(f"   Baseline: {self.config.baseline_duration:.1f}s")
                print(f"   Current avg: {metrics['avg_student_duration']:.1f}s ({degradation_pct:.0f}% of baseline)")
                print(f"   Max acceptable: {max_acceptable_duration:.1f}s ({self.config.acceptable_degradation_multiplier:.0%} of baseline)")
        
        print(f"✅ Test passed worst-case criteria:")
        print(f"   Success rate: {metrics['success_rate']:.1%} (ALL students succeeded)")
        print(f"   Total duration: {metrics['total_duration']:.1f}s")
        print(f"   Avg student duration: {metrics['avg_student_duration']:.1f}s")
        
        return True
    
    def find_max_capacity(self) -> int:
        """
        Use binary search to find maximum capacity.
        Returns the maximum number of students the system can handle.
        """
        print(f"\n{'='*80}")
        print(f"🔍 CAPACITY FINDER - Binary Search (WORST CASE)")
        print(f"{'='*80}")
        print(f"Search range: {self.config.min_students} - {self.config.max_students} students")
        print(f"Success criteria: {self.config.min_success_rate:.0%} success rate (ALL must succeed)")
        print(f"                  <{self.config.max_duration}s duration")
        print(f"                  No timeouts tolerated (timeouts already generous)")
        print(f"                  Performance within {self.config.acceptable_degradation_multiplier:.0%} of baseline")
        print(f"{'='*80}\n")
        
        # Step 1: Establish baseline with single student
        print(f"📊 STEP 1: Establishing baseline performance (1 student)")
        print(f"{'─'*80}")
        baseline_success, baseline_metrics = self.test_capacity(1)
        self.test_results.append(baseline_metrics)
        
        if not baseline_success:
            print(f"\n❌ FATAL: Cannot establish baseline - single student test failed!")
            print(f"   Check your infrastructure setup before running capacity tests.")
            return 0
        
        # Set baseline duration
        self.config.baseline_duration = baseline_metrics['avg_student_duration']
        self.baseline_measured = True
        
        print(f"\n✅ Baseline established:")
        print(f"   Single student duration: {self.config.baseline_duration:.1f}s")
        print(f"   Maximum acceptable avg duration: {self.config.baseline_duration * self.config.acceptable_degradation_multiplier:.1f}s")
        print(f"   ({self.config.acceptable_degradation_multiplier:.0%} degradation tolerance)")
        
        # Step 2: Binary search for max capacity
        print(f"\n{'─'*80}")
        print(f"📊 STEP 2: Binary search for maximum capacity")
        print(f"{'─'*80}\n")
        
        low = 2  # Start at 2 since we already tested 1
        high = self.config.max_students
        max_working = 1  # We know 1 works from baseline
        
        iteration = 0
        
        while low <= high and iteration < self.config.max_iterations:
            iteration += 1
            mid = (low + high) // 2
            
            print(f"\n🔄 Iteration {iteration}/{self.config.max_iterations}")
            print(f"   Current range: [{low}, {high}]")
            print(f"   Testing: {mid} students")
            print(f"   Max working so far: {max_working} students")
            
            success, metrics = self.test_capacity(mid)
            self.test_results.append(metrics)
            
            if success:
                # System handled this load, try higher
                max_working = max(max_working, mid)
                self.max_working_capacity = max_working
                print(f"✅ Success! System handled {mid} students")
                print(f"   → Trying higher: {mid + 1} - {high}")
                low = mid + 1
            else:
                # System failed at this load, try lower
                print(f"❌ Failed at {mid} students")
                print(f"   → Trying lower: {low} - {mid - 1}")
                high = mid - 1
        
        print(f"\n{'='*80}")
        print(f"🎯 CAPACITY SEARCH COMPLETE")
        print(f"{'='*80}")
        print(f"Maximum working capacity: {max_working} students")
        print(f"Total containers: {max_working * 3}")
        print(f"Iterations performed: {iteration}")
        
        return max_working
    
    def _create_test_csv(self, num_students: int) -> str:
        """Create a temporary CSV file for testing"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
        writer = csv.writer(temp_file)
        writer.writerow(['student_id', 'student_name', 'port', 'subnet_id'])
        
        for i in range(num_students):
            student_id = f"captest{i+1:03d}"
            student_name = f"Capacity Test Student {i+1}"
            writer.writerow([student_id, student_name, '', ''])
        
        temp_file.close()
        return temp_file.name
    
    def _read_student_assignments(self, csv_path: str) -> List[Dict]:
        """Read student assignments from CSV"""
        students = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['port']:
                    students.append(row)
        return students
    
    def print_summary_report(self):
        """Print a comprehensive summary of all capacity tests"""
        print(f"\n{'='*80}")
        print(f"📊 CAPACITY TEST SUMMARY REPORT")
        print(f"{'='*80}\n")
        
        if self.config.baseline_duration:
            print(f"Baseline Performance (1 student): {self.config.baseline_duration:.1f}s")
            print(f"Acceptable Degradation: {self.config.acceptable_degradation_multiplier:.0%} ({self.config.baseline_duration * self.config.acceptable_degradation_multiplier:.1f}s max avg)")
        print(f"Maximum Capacity Found: {self.max_working_capacity} students")
        print(f"Total Tests Performed: {len(self.test_results)}")
        print(f"\nDetailed Results:")
        print(f"{'─'*80}")
        
        for i, metrics in enumerate(self.test_results, 1):
            status = "✅ PASS" if metrics.get('success_rate', 0) >= self.config.min_success_rate else "❌ FAIL"
            print(f"\nTest {i}: {metrics['num_students']} students - {status}")
            print(f"  Containers: {metrics.get('total_containers', 0)}")
            print(f"  Success Rate: {metrics.get('success_rate', 0):.1%}")
            print(f"  Total Duration: {metrics.get('total_duration', 0):.1f}s")
            print(f"  Avg Student Duration: {metrics.get('avg_student_duration', 0):.1f}s", end="")
            
            # Show degradation relative to baseline
            if self.config.baseline_duration and metrics.get('avg_student_duration', 0) > 0:
                degradation = (metrics['avg_student_duration'] / self.config.baseline_duration) * 100
                print(f" ({degradation:.0f}% of baseline)")
            else:
                print()
            
            print(f"  Throughput: {metrics.get('students_per_second', 0):.2f} students/sec")
            
            if 'failure_reason' in metrics:
                print(f"  Failure: {metrics['failure_reason']}")
        
        print(f"\n{'='*80}")
        print(f"💡 RECOMMENDATIONS")
        print(f"{'='*80}")
        print(f"Your system can reliably handle: {self.max_working_capacity} students")
        print(f"Recommended safe capacity: {int(self.max_working_capacity * 0.8)} students (80% of max)")
        print(f"This provides headroom for peak usage and system overhead.")
        if self.config.baseline_duration:
            print(f"\nPerformance baseline: {self.config.baseline_duration:.1f}s per student (single-student scenario)")
            print(f"Degradation tolerance: {self.config.acceptable_degradation_multiplier:.0%} (up to {self.config.baseline_duration * self.config.acceptable_degradation_multiplier:.1f}s avg allowed)")
        print(f"{'='*80}\n")


@pytest.mark.capacity
@pytest.mark.manual
class TestCapacityFinder:
    """Capacity testing - finds maximum student load via binary search"""
    
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
        """Setup and teardown for capacity testing"""
        project_root = os.path.dirname(os.path.dirname(__file__))
        sys.path.insert(0, project_root)
        from lab_manager import LabManager
        
        # Auto-detect if sudo is needed for Docker
        use_sudo = self._needs_sudo_for_docker()
        print(f"\n🔧 Using sudo for Docker: {use_sudo}")
        
        self.lab_manager = LabManager(use_sudo=use_sudo)
        self.tester = CapacityTester(self.lab_manager)
        
        yield
        
        # Print final report
        self.tester.print_summary_report()
    
    def test_find_max_capacity(self):
        """
        Find the maximum number of students this system can handle.
        
        This test uses binary search to efficiently find the breaking point.
        It will test progressively larger student counts until it finds the maximum.
        
        WARNING: This test can take 30+ minutes and will stress your system!
        Only run on hardware that matches your production environment.
        """
        max_capacity = self.tester.find_max_capacity()
        
        # Assert that we found at least some capacity
        assert max_capacity >= 1, "System cannot handle even 1 student - check your setup"
        
        print(f"\n✅ Capacity test complete: {max_capacity} students maximum")


if __name__ == "__main__":
    """
    Run capacity test directly (not via pytest)
    Usage: python tests/test_capacity.py
    """
    print("🚀 Starting Capacity Finder (Direct Execution)")
    print("=" * 80)
    print("This will test your system's capacity using binary search.")
    print("It may take 30+ minutes and will stress your system.")
    print("=" * 80)
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Cancelled by user")
        sys.exit(0)
    
    # Set up lab manager
    project_root = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, project_root)
    from lab_manager import LabManager
    
    # Auto-detect if sudo is needed for Docker
    def _needs_sudo_for_docker() -> bool:
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
    
    use_sudo = _needs_sudo_for_docker()
    print(f"\n🔧 Using sudo for Docker: {use_sudo}")
    
    lab_manager = LabManager(use_sudo=use_sudo)
    tester = CapacityTester(lab_manager)
    
    # Run capacity finder
    max_capacity = tester.find_max_capacity()
    
    # Print report
    tester.print_summary_report()
    
    sys.exit(0 if max_capacity >= 1 else 1)
