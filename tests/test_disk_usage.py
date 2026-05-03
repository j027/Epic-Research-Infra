#!/usr/bin/env python3
"""
Disk Usage Measurement Tool for Lab Documentation

Measures actual Docker image sizes and per-student container writable layer
overhead across three stages so instructors can accurately document disk
requirements:

  Best case   — fresh containers, no student activity
  After lab   — one student has completed the full recon + attack + defense lab
  Worst case  — after lab + full apt-get upgrade across all containers

Run with:
    python -m pytest tests/test_disk_usage.py -v -s -m disk_usage
"""

import os
import subprocess
import sys
import time
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lab_manager import LabManager
from tests.conftest import create_csv_with_data
from tests.test_load import StudentSimulator


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_bytes(n: float) -> str:
    """Human-readable byte count."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


IMAGE_NAMES = {
    "kali-jump":      "epic-research-infra-kali-jump:latest",
    "ubuntu-target1": "epic-research-infra-ubuntu-target1:latest",
    "ubuntu-target2": "epic-research-infra-ubuntu-target2:latest",
}


def _container_names(student_id: str) -> dict:
    """Return {label: docker_container_name} for one student."""
    return {
        "kali-jump":      f"kali-jump-{student_id}",
        "ubuntu-target1": f"file-server-{student_id}",
        "ubuntu-target2": f"build-server-{student_id}",
    }


# ── core measurement class ────────────────────────────────────────────────────

class DiskUsageMeasurer:
    """Thin wrapper around docker CLI for disk measurements."""

    def __init__(self, lab_manager: LabManager):
        self.lm = lab_manager

    def image_sizes(self) -> dict:
        """Return {label: bytes} for each lab image. None if image is missing."""
        sizes = {}
        for label, image in IMAGE_NAMES.items():
            try:
                result = self.lm.run_command(
                    ["docker", "image", "inspect", "--format", "{{.Size}}", image]
                )
                sizes[label] = int(result.stdout.strip())
            except subprocess.CalledProcessError:
                print(f"  ⚠️  Image {image} not found — run './lab_manager.py build' first")
                sizes[label] = None
        return sizes

    def container_writable_sizes(self, student_id: str) -> dict:
        """Return {label: bytes} for the writable layer of each container."""
        sizes = {}
        for label, cname in _container_names(student_id).items():
            try:
                result = self.lm.run_command(
                    ["docker", "inspect", "--size", "--format", "{{.SizeRw}}", cname]
                )
                sizes[label] = int(result.stdout.strip())
            except (subprocess.CalledProcessError, ValueError):
                print(f"  ⚠️  Could not read writable size for container {cname}")
                sizes[label] = None
        return sizes

    def run_apt_upgrade(self, student_id: str) -> None:
        """Run apt-get upgrade inside all three containers (worst-case simulation)."""
        for label, cname in _container_names(student_id).items():
            print(f"\n  📦 apt-get upgrade in {label} ({cname})…")
            try:
                self.lm.run_command([
                    "docker", "exec",
                    "--env", "DEBIAN_FRONTEND=noninteractive",
                    cname,
                    "apt-get", "update", "-qq",
                ], capture_output=False)
                self.lm.run_command([
                    "docker", "exec",
                    "--env", "DEBIAN_FRONTEND=noninteractive",
                    cname,
                    "apt-get", "upgrade", "-y", "-qq",
                ], capture_output=False)
                print(f"  ✅ upgrade complete in {label}")
            except subprocess.CalledProcessError as exc:
                print(f"  ⚠️  upgrade failed in {label}: {exc}")

    # ── report ────────────────────────────────────────────────────────────────

    @staticmethod
    def print_report(
        image_sizes: dict,
        best_case: dict,
        after_lab: dict,
        worst_case: dict,
    ) -> None:
        w = 72
        print("\n" + "=" * w)
        print("  DISK USAGE MEASUREMENT REPORT")
        print("=" * w)

        # ── shared images ──────────────────────────────────────────────────
        print("\n  SHARED IMAGE SIZES  (paid once per host, not per student)")
        print(f"  {'Image':<20} {'Size':>10}")
        print(f"  {'-'*20} {'-'*10}")
        total_images = 0
        for label, sz in image_sizes.items():
            if sz is not None:
                total_images += sz
                print(f"  {label:<20} {_fmt_bytes(sz):>10}")
            else:
                print(f"  {label:<20} {'N/A':>10}")
        print(f"  {'TOTAL':<20} {_fmt_bytes(total_images):>10}")

        # ── per-student writable layers ────────────────────────────────────
        print("\n  PER-STUDENT WRITABLE LAYER  (scales linearly with student count)")
        hdr = f"  {'Container':<20} {'Best case':>11}  {'After lab':>11}  {'Worst case':>11}"
        print(hdr)
        print(f"  {'-'*20} {'-'*11}  {'-'*11}  {'-'*11}")
        total_best = total_lab = total_worst = 0
        for label in IMAGE_NAMES:
            b = best_case.get(label)
            l = after_lab.get(label)
            w_ = worst_case.get(label)
            b_str  = _fmt_bytes(b)  if b  is not None else "N/A"
            l_str  = _fmt_bytes(l)  if l  is not None else "N/A"
            w_str  = _fmt_bytes(w_) if w_ is not None else "N/A"
            if b  is not None: total_best  += b
            if l  is not None: total_lab   += l
            if w_ is not None: total_worst += w_
            print(f"  {label:<20} {b_str:>11}  {l_str:>11}  {w_str:>11}")
        print(
            f"  {'TOTAL (per student)':<20} {_fmt_bytes(total_best):>11}"
            f"  {_fmt_bytes(total_lab):>11}  {_fmt_bytes(total_worst):>11}"
        )

        # ── capacity planning ──────────────────────────────────────────────
        print("\n  CAPACITY PLANNING FORMULA")
        print("  Total disk = (shared images) + (N students × writable overhead)")
        print()
        print(f"  Shared images:                   {_fmt_bytes(total_images)}")
        print(f"  Best-case per student:            {_fmt_bytes(total_best)}")
        print(f"  After-lab per student:            {_fmt_bytes(total_lab)}")
        print(f"  Worst-case per student:           {_fmt_bytes(total_worst)}"
              "  ← use this + buffer")
        print()
        print("  Example — 30 students (worst case):")
        if total_images and total_worst:
            example = total_images + 30 * total_worst
            print(
                f"    {_fmt_bytes(total_images)} + 30 × {_fmt_bytes(total_worst)}"
                f" = {_fmt_bytes(example)}"
            )
        print("=" * w)


# ── pytest test ───────────────────────────────────────────────────────────────

@pytest.mark.disk_usage
class TestDiskUsage:
    """
    Three-stage disk measurement:
      1. Best case  — fresh containers, no activity
      2. After lab  — after one student completes the full lab simulation
      3. Worst case — after lab + full apt-get upgrade across all containers

    Run manually — NOT included in CI.
    """

    TEST_STUDENT_ID   = "disktest001"
    TEST_STUDENT_NAME = "Disk Test Student"
    TEST_PORT         = 29990
    TEST_SUBNET_ID    = 253   # High subnet to avoid clashing with real students
    TEST_PASSWORD     = "student123"

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        use_sudo = LabManager._detect_sudo_needed()
        self.lm = LabManager(use_sudo=use_sudo)
        self.measurer = DiskUsageMeasurer(self.lm)
        self.csv_file = None
        yield
        self._teardown()

    # ── private helpers ───────────────────────────────────────────────────────

    def _teardown(self):
        print("\n🧹 Tearing down disk-test containers…")
        sid = self.TEST_STUDENT_ID
        env = self.lm.get_student_env(
            sid, self.TEST_STUDENT_NAME, self.TEST_PORT,
            subnet_id=self.TEST_SUBNET_ID, csv_file="students.csv",
        )
        try:
            self.lm.run_command([
                "docker", "compose",
                "-f", self.lm.compose_file,
                "-p", f"cyber-lab-{sid}",
                "down", "--volumes", "--remove-orphans",
            ], env=env, capture_output=False)
        except subprocess.CalledProcessError as exc:
            print(f"  ⚠️  Teardown error (containers may already be gone): {exc}")

        if self.csv_file and os.path.exists(self.csv_file):
            os.unlink(self.csv_file)

    def _spin_up(self) -> bool:
        tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv")
        tf.close()
        self.csv_file = tf.name
        create_csv_with_data(self.csv_file, [{
            "student_id":   self.TEST_STUDENT_ID,
            "student_name": self.TEST_STUDENT_NAME,
            "port":         str(self.TEST_PORT),
            "subnet_id":    str(self.TEST_SUBNET_ID),
            "password":     self.TEST_PASSWORD,
        }])
        return self.lm.spin_up_student(
            self.TEST_STUDENT_ID,
            self.TEST_STUDENT_NAME,
            self.TEST_PORT,
            subnet_id=self.TEST_SUBNET_ID,
            password=self.TEST_PASSWORD,
            csv_file=self.csv_file,
        )

    def _wait_for_containers(self, timeout: int = 60) -> bool:
        expected = list(_container_names(self.TEST_STUDENT_ID).values())
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = self.lm.run_command(["docker", "ps", "--format", "{{.Names}}"])
                running = result.stdout.strip().split("\n")
                if all(c in running for c in expected):
                    return True
            except subprocess.CalledProcessError:
                pass
            time.sleep(2)
        return False

    def _run_lab_simulation(self) -> dict:
        """Run the full student lab simulation (recon + attack + defense)."""
        sim = StudentSimulator(
            student_id=self.TEST_STUDENT_ID,
            student_name=self.TEST_STUDENT_NAME,
            host="localhost",
            port=self.TEST_PORT,
            realistic_mode=False,
        )
        sim.current_password = self.TEST_PASSWORD
        return sim.run_full_simulation()

    # ── test ─────────────────────────────────────────────────────────────────

    def test_measure_disk_usage(self):
        """
        Spin up containers, measure disk at each stage, then print planning report.
        """
        print("\n" + "=" * 60)
        print("  DISK USAGE MEASUREMENT — starting")
        print("=" * 60)

        # ── stage 0: image sizes ──────────────────────────────────────────
        print("\n[1/6] Measuring shared image sizes…")
        image_sizes = self.measurer.image_sizes()
        if all(v is None for v in image_sizes.values()):
            pytest.skip("No lab images found. Build them first: ./lab_manager.py build")

        # ── stage 1: spin up ──────────────────────────────────────────────
        print(f"\n[2/6] Spinning up test student ({self.TEST_STUDENT_ID})…")
        assert self._spin_up(), "Failed to spin up test student containers"
        print("\n[3/6] Waiting for containers to be ready…")
        assert self._wait_for_containers(), "Containers did not become ready within timeout"

        # ── stage 2: best-case measurement ───────────────────────────────
        print("\n[4/6] Measuring best-case (fresh container) writable layer sizes…")
        best_case = self.measurer.container_writable_sizes(self.TEST_STUDENT_ID)

        # ── stage 3: full lab simulation ──────────────────────────────────
        print("\n[5/6] Running full lab simulation (recon + attack + defense)…")
        sim_result = self._run_lab_simulation()
        successful = sim_result.get("successful_steps", 0)
        total = sim_result.get("total_steps", 0)
        duration = sim_result.get("total_duration", 0)
        print(
            f"  Simulation finished: {successful}/{total} steps succeeded "
            f"in {duration:.1f}s"
        )
        after_lab = self.measurer.container_writable_sizes(self.TEST_STUDENT_ID)

        # ── stage 4: worst-case apt upgrade ──────────────────────────────
        print("\n[6/6] Simulating worst-case: apt-get upgrade in all containers…")
        self.measurer.run_apt_upgrade(self.TEST_STUDENT_ID)
        worst_case = self.measurer.container_writable_sizes(self.TEST_STUDENT_ID)

        # ── report ────────────────────────────────────────────────────────
        DiskUsageMeasurer.print_report(image_sizes, best_case, after_lab, worst_case)
