"""
Tests for system_check.py — hardware probe + model recommendation.

These tests exercise the recommendation tiers without spinning up FastAPI; we
call the inner handler functions directly via TestClient since they're closures
inside create_system_routes(). For unit-level coverage we also test the pure
SystemChecker class.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.system_check import (
    SystemChecker,
    SystemRequirements,
    HardwareInfo,
    create_system_routes,
    _detect_gpu,
)


def _make_app():
    app = FastAPI()
    app.include_router(create_system_routes())
    return TestClient(app)


class TestSystemChecker:
    def test_check_all_requirements_returns_expected_keys(self):
        checker = SystemChecker()
        result = checker.check_all_requirements()
        assert "meets_requirements" in result
        assert "hardware" in result
        assert "checks" in result
        assert {c["name"] for c in result["checks"]} == {"RAM", "CPU Cores", "Disk Space"}

    def test_fail_status_when_below_minimum(self):
        # Requirements impossible to meet → status fail
        impossible = SystemRequirements(
            ram_minimum_gb=999.0, ram_recommended_gb=999.0,
            cpu_cores_minimum=999, cpu_cores_recommended=999,
            disk_minimum_gb=99999.0, disk_recommended_gb=99999.0,
        )
        checker = SystemChecker(requirements=impossible)
        result = checker.check_all_requirements()
        assert result["meets_requirements"] is False
        assert result["overall_status"] == "fail"


class TestRecommendModel:
    def test_recommends_high_tier_for_gpu_plus_16gb(self):
        client = _make_app()
        fake_hw = HardwareInfo(
            ram_total_gb=32.0, ram_available_gb=20.0,
            cpu_cores=8, cpu_name="x86",
            disk_free_gb=200.0, disk_total_gb=500.0,
            os_name="Linux", os_version="6.0", python_version="3.11.0",
        )
        with patch("app.system_check.SystemChecker.get_hardware_info", return_value=fake_hw), \
             patch("app.system_check._detect_gpu", return_value={"type": "nvidia", "name": "RTX 4080", "vram_gb": 16.0}):
            r = client.get("/api/system/recommend-model")
        assert r.status_code == 200
        body = r.json()
        assert body["recommended_model"] == "llama3.1:8b"
        assert body["quality"] == "excellent"
        assert body["hardware"]["gpu"]["type"] == "nvidia"
        assert "ollama pull" in body["ollama_pull_command"]

    def test_recommends_baseline_for_8gb_no_gpu(self):
        client = _make_app()
        fake_hw = HardwareInfo(
            ram_total_gb=8.0, ram_available_gb=4.0,
            cpu_cores=4, cpu_name="x86",
            disk_free_gb=50.0, disk_total_gb=250.0,
            os_name="Linux", os_version="6.0", python_version="3.11.0",
        )
        with patch("app.system_check.SystemChecker.get_hardware_info", return_value=fake_hw), \
             patch("app.system_check._detect_gpu", return_value={"type": "unknown", "name": "n/a", "vram_gb": None}):
            r = client.get("/api/system/recommend-model")
        assert r.status_code == 200
        assert r.json()["recommended_model"] == "llama3.2:3b"

    def test_falls_back_to_smallest_on_constrained_hw(self):
        client = _make_app()
        fake_hw = HardwareInfo(
            ram_total_gb=2.0, ram_available_gb=1.0,
            cpu_cores=2, cpu_name="armv7",
            disk_free_gb=10.0, disk_total_gb=32.0,
            os_name="Linux", os_version="6.0", python_version="3.11.0",
        )
        with patch("app.system_check.SystemChecker.get_hardware_info", return_value=fake_hw), \
             patch("app.system_check._detect_gpu", return_value={"type": "unknown", "name": "n/a", "vram_gb": None}):
            r = client.get("/api/system/recommend-model")
        assert r.status_code == 200
        # 2 cores < 4 → llama3.2:1b
        assert r.json()["recommended_model"] == "llama3.2:1b"

    def test_detect_gpu_never_raises(self):
        # Even on a CI box without nvidia-smi/rocm-smi this must return a dict.
        info = _detect_gpu()
        assert isinstance(info, dict)
        assert "type" in info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
