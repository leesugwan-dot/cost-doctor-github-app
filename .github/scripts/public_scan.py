#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
MAX_REPO_KB = 50000
URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
HEADING = "### GitHub 저장소 주소"


def api(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "costdoctor-public-scan")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def extract_repo_url(body):
    marker = body.find(HEADING)
    if marker < 0:
        raise ValueError("URL_FIELD_MISSING")
    tail = body[marker + len(HEADING):]
    for line in tail.splitlines():
        value = line.strip()
        if not value or value.startswith("###"):
            continue
        return value
    raise ValueError("URL_FIELD_MISSING")


def normalize_repo(value):
    m = URL_RE.fullmatch(value.strip())
    if not m:
        raise ValueError("URL_INVALID")
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def post_comment(repository, issue_number, token, text):
    api("POST", f"{API}/repos/{repository}/issues/{issue_number}/comments", token, {"body": text[:60000]})


def close_issue(repository, issue_number, token):
    api("PATCH", f"{API}/repos/{repository}/issues/{issue_number}", token, {"state": "closed"})


def run(cmd, *, cwd=None, env=None, timeout=240):
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    issue = event["issue"]
    issue_number = int(issue["number"])
    title = issue.get("title", "")

    if not title.startswith("[CostDoctor Scan]"):
        return 0

    target_repo = None
    try:
        target_repo = normalize_repo(extract_repo_url(issue.get("body") or ""))
        owner, repo = target_repo.split("/", 1)
        meta = api("GET", f"{API}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}", token)
        if meta.get("private"):
            raise ValueError("PUBLIC_REPO_REQUIRED")
        if meta.get("disabled"):
            raise ValueError("REPOSITORY_DISABLED")
        if int(meta.get("size") or 0) > MAX_REPO_KB:
            raise ValueError("REPO_TOO_LARGE_FOR_PUBLIC_BETA")

        target_dir = runner_temp / f"costdoctor-target-{issue_number}"
        result_dir = runner_temp / f"costdoctor-result-{issue_number}"
        if target_dir.exists() or result_dir.exists():
            raise RuntimeError("TEMP_PATH_EXISTS")

        clone_url = f"https://github.com/{target_repo}.git"
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        run([
            "git", "-c", "protocol.file.allow=never", "clone",
            "--depth=1", "--single-branch", "--no-tags", "--recurse-submodules=no",
            "--filter=blob:limit=262144", clone_url, str(target_dir)
        ], env=env, timeout=180)

        head = run(["git", "-C", str(target_dir), "rev-parse", "HEAD"], timeout=20).stdout.strip()
        if not re.fullmatch(r"[a-f0-9]{40}", head):
            raise RuntimeError("HEAD_INVALID")

        cli = workspace / "costdoctor-entry" / "entry" / "cli.mjs"
        proc = run(["node", str(cli), "--repo", str(target_dir), "--output", str(result_dir), "--head", head], timeout=120)
        report_path = result_dir / "report.md"
        if not report_path.is_file():
            raise RuntimeError("REPORT_MISSING")
        report = report_path.read_text(encoding="utf-8")

        text = (
            "## CostDoctor 무료 공개 저장소 진단 결과\n\n"
            f"대상: `{target_repo}`  \n"
            f"고정 commit: `{head}`\n\n"
            + report
            + "\n---\n"
            "이 결과는 **정적 진단**입니다. 실제 호출 수·비용·토큰 절감·품질 개선을 증명하지 않습니다. "
            "대상 코드는 실행하지 않았고, 원문 코드·파일명·비밀정보는 결과 댓글에 포함하지 않습니다. "
            "분석용 checkout은 GitHub-hosted runner의 임시 작업공간에서만 사용됩니다.\n"
        )
        post_comment(repository, issue_number, token, text)
        close_issue(repository, issue_number, token)
        return 0

    except urllib.error.HTTPError as e:
        code = "REPOSITORY_UNAVAILABLE" if e.code in (404, 403) else "GITHUB_API_ERROR"
    except subprocess.TimeoutExpired:
        code = "SCAN_TIMEOUT"
    except subprocess.CalledProcessError:
        code = "SCAN_FAILED"
    except ValueError as e:
        code = str(e) if re.fullmatch(r"[A-Z0-9_]+", str(e)) else "INPUT_INVALID"
    except Exception:
        code = "INTERNAL_ERROR"

    try:
        target_line = f"대상: `{target_repo}`\n\n" if target_repo else ""
        post_comment(
            repository, issue_number, token,
            "## CostDoctor 진단을 완료하지 못했습니다\n\n"
            + target_line
            + f"상태: **{code}**\n\n"
            "공개 GitHub 저장소 주소인지 확인한 뒤 새 진단 요청을 만들어 주세요. "
            "비공개 저장소는 이 무료 공개 진단에서 읽지 않습니다.\n"
        )
        close_issue(repository, issue_number, token)
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
