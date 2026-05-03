"""
Tests for auto_updater.py - Auto-update mechanism
"""
import pytest
import sys
import os
import json

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from auto_updater import AutoUpdater, ReleaseInfo


class TestAutoUpdater:
    """Test suite for AutoUpdater"""

    def test_updater_initialization(self):
        """Test that updater initializes correctly"""
        updater = AutoUpdater(current_version="1.0.0")
        assert updater.current_version == "1.0.0"

    def test_version_comparison_newer(self):
        """Test version comparison when update is newer"""
        updater = AutoUpdater(current_version="1.0.0")

        assert updater._is_newer_version("1.0.1") is True
        assert updater._is_newer_version("1.1.0") is True
        assert updater._is_newer_version("2.0.0") is True

    def test_version_comparison_older(self):
        """Test version comparison when update is older"""
        updater = AutoUpdater(current_version="2.0.0")

        assert updater._is_newer_version("1.9.9") is False
        assert updater._is_newer_version("1.0.0") is False

    def test_version_comparison_equal(self):
        """Test version comparison when versions are equal"""
        updater = AutoUpdater(current_version="1.0.0")
        assert updater._is_newer_version("1.0.0") is False

    def test_version_comparison_complex(self):
        """Test version comparison with complex versions"""
        updater = AutoUpdater(current_version="1.2.3")

        assert updater._is_newer_version("1.2.4") is True
        assert updater._is_newer_version("1.3.0") is True
        assert updater._is_newer_version("1.2.2") is False
        assert updater._is_newer_version("1.1.10") is False

    def test_version_comparison_with_v_prefix(self):
        """Test version comparison handles v prefix"""
        updater = AutoUpdater(current_version="1.0.0")
        assert updater._is_newer_version("v1.0.1") is True
        assert updater._is_newer_version("v0.9.0") is False

    def test_parse_version(self):
        """Test version string parsing"""
        updater = AutoUpdater(current_version="1.0.0")
        assert updater._parse_version("1.2.3") == (1, 2, 3)
        assert updater._parse_version("v1.2.3") == (1, 2, 3)
        assert updater._parse_version("1.2.3-beta") == (1, 2, 3)


class TestReleaseInfo:
    """Test ReleaseInfo dataclass"""

    def test_release_info_creation(self):
        """Test creating ReleaseInfo"""
        info = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            name="Release 2.0.0",
            body="Bug fixes and improvements",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com/update.zip",
            size=10485760,
            sha256="abc123",
        )

        assert info.version == "2.0.0"
        assert info.tag_name == "v2.0.0"
        assert info.download_url == "https://example.com/update.zip"
        assert info.size == 10485760
        assert info.sha256 == "abc123"


class TestConfig:
    """Test update configuration"""

    def test_default_config(self):
        """Test default config values"""
        updater = AutoUpdater(current_version="1.0.0")

        assert updater.config["auto_check"] is True
        assert updater.config["check_interval_hours"] == 24
        assert updater.config["auto_download"] is False
        assert updater.config["auto_install"] is False
        assert updater.config["update_channel"] == "stable"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
