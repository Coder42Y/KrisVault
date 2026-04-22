import json
import sys

import pytest
from io import StringIO

from scripts.fetch_repo import (
    detect_platform,
    parse_repo_url,
    is_binary_file,
    fetch_repo,
)


# ---------------------------------------------------------------------------
# detect_platform
# ---------------------------------------------------------------------------

def test_detect_platform_github():
    assert detect_platform("https://github.com/songquanpeng/one-api") == "github"


def test_detect_platform_gitlab():
    assert detect_platform("https://gitlab.com/user/project") == "gitlab"


def test_detect_platform_gitlab_selfhosted():
    assert detect_platform("https://git.company.com/user/project") == "gitlab"


def test_detect_platform_invalid():
    with pytest.raises(ValueError, match="Unsupported platform"):
        detect_platform("https://bitbucket.org/user/project")


# ---------------------------------------------------------------------------
# parse_repo_url
# ---------------------------------------------------------------------------

def test_parse_repo_url_github_basic():
    assert parse_repo_url("https://github.com/songquanpeng/one-api") == ("songquanpeng", "one-api", "main")


def test_parse_repo_url_github_with_branch():
    assert parse_repo_url("https://github.com/songquanpeng/one-api/tree/dev") == ("songquanpeng", "one-api", "dev")


def test_parse_repo_url_gitlab_basic():
    assert parse_repo_url("https://gitlab.com/user/project") == ("user", "project", "main")


def test_parse_repo_url_gitlab_with_branch():
    assert parse_repo_url("https://gitlab.com/user/project/-/tree/release") == ("user", "project", "release")


def test_parse_repo_url_invalid():
    with pytest.raises(ValueError, match="Invalid repository URL"):
        parse_repo_url("https://github.com/")


# ---------------------------------------------------------------------------
# is_binary_file
# ---------------------------------------------------------------------------

def test_is_binary_file_by_extension():
    assert is_binary_file("image.png") is True
    assert is_binary_file("image.jpg") is True
    assert is_binary_file("main.go") is False


def test_is_binary_file_by_size():
    assert is_binary_file("bigfile.txt", size=2 * 1024 * 1024) is True
    assert is_binary_file("smallfile.txt", size=1024) is False


# ---------------------------------------------------------------------------
# fetch_repo (integration with mocked network)
# ---------------------------------------------------------------------------

def test_fetch_repo_list_only_mocked(monkeypatch):
    """Integration test with mocked GitHub API."""
    import requests

    class FakeResp:
        status_code = 200
        def json(self):
            return {
                "tree": [
                    {"path": "README.md", "type": "blob", "size": 50},
                    {"path": "main.go", "type": "blob", "size": 200},
                ]
            }

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResp())

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        fetch_repo("https://github.com/octocat/Hello-World", list_only=True)
        output = sys.stdout.getvalue()
        data = json.loads(output)
        assert data["platform"] == "github"
        assert data["owner"] == "octocat"
        assert data["repo"] == "Hello-World"
        assert len(data["files"]) == 2
    finally:
        sys.stdout = old_stdout
