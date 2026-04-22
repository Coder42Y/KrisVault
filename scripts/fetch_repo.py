"""Fetch repository content from GitHub or GitLab."""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


def detect_platform(url: str) -> str:
    """Detect if URL is GitHub or GitLab (including self-hosted)."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if hostname == "github.com" or hostname.endswith(".github.com"):
        return "github"
    if hostname == "gitlab.com" or hostname.endswith(".gitlab.com"):
        return "gitlab"
    # Explicitly reject known unsupported platforms
    unsupported = {"bitbucket.org"}
    if hostname in unsupported:
        raise ValueError(f"Unsupported platform: {url}")
    # Self-hosted GitLab: treat any other hostname as gitlab for now
    if hostname:
        return "gitlab"
    raise ValueError(f"Unsupported platform: {url}")


def parse_repo_url(url: str) -> tuple:
    """Parse (owner, repo, branch) from a repo URL.

    Supports:
      https://github.com/owner/repo
      https://github.com/owner/repo/tree/branch
      https://gitlab.com/owner/repo
      https://gitlab.com/owner/repo/-/tree/branch
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")

    if len(parts) < 2:
        raise ValueError(f"Invalid repository URL: {url}")

    owner = parts[0]
    repo = parts[1]
    branch = "main"  # default

    # GitHub: /owner/repo/tree/branch
    if "tree" in parts:
        idx = parts.index("tree")
        if idx + 1 < len(parts):
            branch = parts[idx + 1]

    # GitLab: /owner/repo/-/tree/branch
    if "-" in parts and "tree" in parts:
        idx = parts.index("tree")
        if idx + 1 < len(parts):
            branch = parts[idx + 1]

    return owner, repo, branch


def get_auth_headers(platform: str) -> dict:
    """Return Authorization headers if token env var is set."""
    token = os.environ.get("GITHUB_TOKEN") if platform == "github" else os.environ.get("GITLAB_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def api_request(url: str, headers: dict, max_retries: int = 3) -> requests.Response:
    """Make an API request with rate-limit handling and retries."""
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "0")
            if remaining == "0":
                reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_seconds = max(0, reset_time - int(time.time()) + 1)
                print(f"Rate limited. Sleeping {sleep_seconds}s...", file=sys.stderr)
                time.sleep(min(sleep_seconds, 60))
                continue
        if resp.status_code in (500, 502, 503):
            wait = 2 ** attempt
            print(f"Server error {resp.status_code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        break
    return resp


def get_tree_github(owner: str, repo: str, branch: str, headers: dict) -> list:
    """Fetch recursive tree from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = api_request(url, headers)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    data = resp.json()
    return data.get("tree", [])


def get_tree_gitlab(owner: str, repo: str, branch: str, headers: dict, base_url: str = "https://gitlab.com") -> list:
    """Fetch recursive tree from GitLab API."""
    project_path = f"{owner}/{repo}"
    encoded_path = quote(project_path, safe="")
    url = (
        f"{base_url}/api/v4/projects/{encoded_path}/repository/tree"
        f"?recursive=true&ref={branch}&per_page=100"
    )

    all_items = []
    page = 1
    while True:
        page_url = f"{url}&page={page}"
        resp = api_request(page_url, headers)
        if resp.status_code != 200:
            raise RuntimeError(f"GitLab API error {resp.status_code}: {resp.text}")
        items = resp.json()
        if not items:
            break
        for item in items:
            all_items.append({
                "path": item["path"],
                "type": "blob" if item["type"] == "blob" else "tree",
                "size": item.get("size", 0),
            })
        if len(items) < 100:
            break
        page += 1
        if page > 50:  # Safety limit
            break
    return all_items


def get_file_content_github(owner: str, repo: str, branch: str, path: str, headers: dict) -> str:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = api_request(url, headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch {path}: {resp.status_code}")
    return resp.text


def get_file_content_gitlab(owner: str, repo: str, branch: str, path: str, headers: dict, base_url: str = "https://gitlab.com") -> str:
    """Fetch raw file content from GitLab."""
    project_path = f"{owner}/{repo}"
    encoded_path = quote(project_path, safe="")
    encoded_file_path = quote(path, safe="")
    url = f"{base_url}/api/v4/projects/{encoded_path}/repository/files/{encoded_file_path}/raw?ref={branch}"
    resp = api_request(url, headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch {path}: {resp.status_code}")
    return resp.text


def is_binary_file(path: str, size: int = 0) -> bool:
    """Heuristic to detect binary files by extension or size."""
    binary_exts = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
        ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
        ".exe", ".dll", ".so", ".dylib",
        ".ttf", ".woff", ".woff2", ".eot",
        ".mp3", ".mp4", ".avi", ".mov", ".webm",
        ".db", ".sqlite", ".sqlite3",
    }
    ext = Path(path).suffix.lower()
    if ext in binary_exts:
        return True
    if size > 1024 * 1024:  # > 1MB
        return True
    return False


def fetch_repo(url: str, list_only: bool = False, files_json: str = None, output_dir: str = "contents", max_files: int = 15):
    """Main entry point."""
    platform = detect_platform(url)
    owner, repo, branch = parse_repo_url(url)
    headers = get_auth_headers(platform)
    base_url = urlparse(url).scheme + "://" + urlparse(url).hostname

    # Get tree
    if platform == "github":
        tree = get_tree_github(owner, repo, branch, headers)
    else:
        tree = get_tree_gitlab(owner, repo, branch, headers, base_url)

    if list_only:
        output = {
            "platform": platform,
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "files": [
                {
                    "path": item.get("path", item.get("name", "")),
                    "type": item.get("type", "blob"),
                    "size": item.get("size", 0),
                }
                for item in tree
            ],
        }
        print(json.dumps(output, indent=2))
        return

    # Download specific files
    if files_json:
        with open(files_json, "r", encoding="utf-8") as f:
            file_data = json.load(f)
            file_list = file_data.get("core_files", file_data.get("files", []))
    else:
        file_list = []

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for entry in file_list[:max_files]:
        path = entry.get("path", "")
        if not path:
            continue

        size = entry.get("size", 0)
        if is_binary_file(path, size):
            print(f"Skipping binary file: {path}", file=sys.stderr)
            continue

        try:
            if platform == "github":
                content = get_file_content_github(owner, repo, branch, path, headers)
            else:
                content = get_file_content_gitlab(owner, repo, branch, path, headers, base_url)

            out_path = Path(output_dir) / path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            downloaded.append(path)
            print(f"Downloaded: {path}")
        except Exception as e:
            print(f"Error downloading {path}: {e}", file=sys.stderr)

    # Write manifest
    manifest = {
        "repo_url": url,
        "platform": platform,
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "downloaded_files": downloaded,
    }
    manifest_path = Path(output_dir) / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDownloaded {len(downloaded)} files to {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch repository content from GitHub or GitLab")
    parser.add_argument("url", help="Repository URL")
    parser.add_argument("--list-only", action="store_true", help="Only list files, don't download")
    parser.add_argument("--files", dest="files_json", help="JSON file containing files to download")
    parser.add_argument("--output-dir", default="contents", help="Output directory for downloaded files")
    parser.add_argument("--max-files", type=int, default=15, help="Maximum files to download")
    args = parser.parse_args()
    fetch_repo(args.url, args.list_only, args.files_json, args.output_dir, args.max_files)
