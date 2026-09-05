#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"
MAX_REPO_KB = 50000
MAX_SCANS_PER_USER_24H = 5
TITLE_PREFIX = "[CostDoctor Scan]"
URL_HEADING = "### GitHub 저장소 주소"
LANG_HEADING = "### 결과 언어 / Result language"
CONFIRM_TEXT = "이 저장소가 공개 저장소이며 진단 결과가 공개 GitHub 이슈에 표시되는 것에 동의합니다."
SUPPORTED_LANGUAGES = {"한국어": "ko", "English": "en"}
RECEIPT_SCHEMA = "costdoctor.public-scan-receipt.v2"


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


def extract_field(body, heading):
    marker = body.find(heading)
    if marker < 0:
        raise ValueError("FORM_FIELD_MISSING")
    tail = body[marker + len(heading):]
    for line in tail.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith("### "):
            break
        if value.startswith("- ["):
            continue
        return value
    raise ValueError("FORM_FIELD_MISSING")


def normalize_repo(value):
    raw = value.strip()
    if "://" not in raw and raw.startswith("github.com/"):
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("URL_INVALID")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("URL_INVALID")
    parts = [urllib.parse.unquote(p) for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("URL_INVALID")
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    allowed = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not allowed.fullmatch(owner) or not allowed.fullmatch(repo):
        raise ValueError("URL_INVALID")
    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("URL_INVALID")
    return f"{owner}/{repo}"


def parse_language(body):
    try:
        value = extract_field(body, LANG_HEADING)
    except ValueError:
        return "ko"
    return SUPPORTED_LANGUAGES.get(value, "ko")


def confirmation_present(body):
    return f"- [x] {CONFIRM_TEXT}" in body or f"- [X] {CONFIRM_TEXT}" in body


def post_comment(repository, issue_number, token, text):
    api("POST", f"{API}/repos/{repository}/issues/{issue_number}/comments", token, {"body": text[:60000]})


def close_issue(repository, issue_number, token):
    api("PATCH", f"{API}/repos/{repository}/issues/{issue_number}", token, {"state": "closed", "state_reason": "completed"})


def lock_issue(repository, issue_number, token):
    api("PUT", f"{API}/repos/{repository}/issues/{issue_number}/lock", token, {"lock_reason": "resolved"})


def close_and_lock(repository, issue_number, token):
    close_issue(repository, issue_number, token)
    try:
        lock_issue(repository, issue_number, token)
    except Exception:
        # Locking is an operational hardening step. A completed scan result must not
        # be turned into a false failure only because GitHub refused the lock call.
        pass


def run(cmd, *, cwd=None, env=None, timeout=240):
    return subprocess.run(
        cmd, cwd=cwd, env=env, timeout=timeout, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def enforce_rate_limit(repository, user, issue_number, token):
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    q = urllib.parse.urlencode({
        "creator": user,
        "state": "all",
        "since": since,
        "per_page": 100,
        "sort": "created",
        "direction": "desc",
    })
    items = api("GET", f"{API}/repos/{repository}/issues?{q}", token) or []
    count = 0
    for item in items:
        if int(item.get("number", -1)) == issue_number:
            continue
        if str(item.get("title", "")).startswith(TITLE_PREFIX):
            count += 1
    if count >= MAX_SCANS_PER_USER_24H:
        raise ValueError("RATE_LIMITED")


def get_target_metadata(target_repo, token):
    owner, repo = target_repo.split("/", 1)
    owner_q = urllib.parse.quote(owner, safe="")
    repo_q = urllib.parse.quote(repo, safe="")
    meta = api("GET", f"{API}/repos/{owner_q}/{repo_q}", token)
    if meta.get("private"):
        raise ValueError("PUBLIC_REPO_REQUIRED")
    if meta.get("disabled"):
        raise ValueError("REPOSITORY_DISABLED")
    if int(meta.get("size") or 0) > MAX_REPO_KB:
        raise ValueError("REPO_TOO_LARGE_FOR_PUBLIC_BETA")
    default_branch = meta.get("default_branch")
    if not default_branch:
        raise ValueError("DEFAULT_BRANCH_MISSING")
    branch_q = urllib.parse.quote(default_branch, safe="")
    branch = api("GET", f"{API}/repos/{owner_q}/{repo_q}/branches/{branch_q}", token)
    head = ((branch or {}).get("commit") or {}).get("sha")
    if not isinstance(head, str) or not re.fullmatch(r"[a-f0-9]{40}", head):
        raise RuntimeError("HEAD_INVALID")
    return {
        "head": head,
        "default_branch": default_branch,
        "language": meta.get("language") or "Unknown",
        "size_kb": int(meta.get("size") or 0),
        "archived": bool(meta.get("archived")),
        "fork": bool(meta.get("fork")),
    }


def clone_exact_snapshot(target_repo, default_branch, expected_head, target_dir, runner_temp):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["HOME"] = str(runner_temp / "git-home")
    Path(env["HOME"]).mkdir(mode=0o700, parents=False, exist_ok=False)

    clone_url = f"https://github.com/{target_repo}.git"
    run([
        "git",
        "-c", "protocol.file.allow=never",
        "-c", "core.hooksPath=/dev/null",
        "-c", "filter.lfs.smudge=",
        "-c", "filter.lfs.required=false",
        "clone",
        "--depth=1",
        "--single-branch",
        "--no-tags",
        "--no-recurse-submodules",
        "--filter=blob:limit=262144",
        "--branch", default_branch,
        clone_url,
        str(target_dir),
    ], env=env, timeout=180)

    actual_head = run(
        ["git", "-c", "protocol.file.allow=never", "-C", str(target_dir), "rev-parse", "HEAD"],
        env=env, timeout=20
    ).stdout.strip()
    if actual_head != expected_head:
        raise RuntimeError("HEAD_MOVED_RETRY")
    return actual_head


def load_report(result_dir):
    report_json = result_dir / "report.json"
    if not report_json.is_file():
        raise RuntimeError("REPORT_MISSING")
    return json.loads(report_json.read_text(encoding="utf-8"))


def top_findings(report, limit=4):
    findings = list(report.get("findings") or [])
    findings.sort(key=lambda x: int(x.get("signal_count") or 0), reverse=True)
    return findings[:limit]


def canonical_sha256(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_tool_sha(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) else "UNKNOWN"


def build_receipt(report, target_repo, meta, issue_url, run_url, tool_sha, generated_at=None):
    coverage = report.get("coverage") or {}
    findings = [
        {"rule": f.get("rule"), "signal_count": int(f.get("signal_count") or 0)}
        for f in top_findings(report)
    ]
    core = {
        "schema": RECEIPT_SCHEMA,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "target": {
            "repository": target_repo,
            "default_branch": meta.get("default_branch"),
            "head": meta.get("head"),
            "primary_language": meta.get("language"),
            "archived": bool(meta.get("archived")),
            "fork": bool(meta.get("fork")),
        },
        "scan": {
            "status": report.get("verdict", "UNKNOWN"),
            "analyzed_files": int(coverage.get("analyzed_files") or 0),
            "analyzed_bytes": int(coverage.get("analyzed_bytes") or 0),
            "findings": findings,
            "scanner_report_sha256": canonical_sha256(report),
        },
        "costdoctor": {"head": safe_tool_sha(tool_sha)},
        "run": {"issue_url": issue_url, "actions_run_url": run_url},
        "claims": {
            "static_review_signals_only": True,
            "actual_calls_measured": False,
            "actual_savings_verified": False,
            "quality_verified": False,
        },
        "privacy": {
            "raw_source_in_public_result": False,
            "filenames_in_public_result": False,
            "credentials_requested": False,
            "private_repository_content_supported": False,
            "operator_personal_pc_used": False,
        },
    }
    receipt = dict(core)
    receipt["receipt_sha256"] = canonical_sha256(core)
    return receipt


def format_result(report, target_repo, meta, lang, issue_url, run_url, receipt=None):
    verdict = report.get("verdict", "UNKNOWN")
    coverage = report.get("coverage") or {}
    analyzed_files = int(coverage.get("analyzed_files") or 0)
    analyzed_bytes = int(coverage.get("analyzed_bytes") or 0)
    findings = top_findings(report)
    receipt_id = (receipt or {}).get("receipt_sha256", "")[:16]
    receipt_line_en = f"  \n**Receipt:** `{receipt_id}` (sanitized receipt is attached to the Actions run)" if receipt_id else ""
    receipt_line_ko = f"  \n**검증 영수증:** `{receipt_id}` (민감정보 없는 receipt는 Actions 실행 Artifact에 포함)" if receipt_id else ""

    if lang == "en":
        labels = {
            "MODEL_CALL": "Model-call candidates",
            "RETRY_LOOP": "Retry-setting candidates",
            "CACHE_SIGNAL": "Cache signals",
            "TOKEN_LIMIT": "Token/context-limit signals",
        }
        rows = "\n".join(
            f"| {labels.get(f.get('rule'), f.get('title', f.get('rule', 'Signal')))} | {int(f.get('signal_count') or 0)} |"
            for f in findings
        ) or "| No matching signal in scanned scope | 0 |"
        return f"""## CostDoctor free public repository scan

**Repository:** `{target_repo}`  
**Status:** `{verdict}`  
**Primary language reported by GitHub:** `{meta['language']}`  
**Scanned:** {analyzed_files} files / {analyzed_bytes} bytes  
**Snapshot:** exact default-branch HEAD verified against the GitHub API before analysis.{receipt_line_en}

| Review signal | Static count |
| --- | ---: |
{rows}

### What this means
- These are **static review signals**, not measured API calls, defects, or proven waste.
- **Actual token/cost savings: UNKNOWN.**
- No target-project code was executed.
- No source code, filenames, credentials, API keys, or private repository content are included in this result.
- The target snapshot was used only in a temporary GitHub-hosted runner workspace for this run.

### Next step
Measure one high-signal path with the same goal/input/model/quality criteria before and after any optimization. A lower cost is not a success if quality or completion drops.

[Scan request]({issue_url}) · [GitHub Actions run]({run_url})
"""
    rows = "\n".join(
        f"| {f.get('title', f.get('rule', '확인 항목'))} | {int(f.get('signal_count') or 0)} |"
        for f in findings
    ) or "| 검사 범위에서 일치 신호 없음 | 0 |"
    return f"""## CostDoctor 무료 공개 저장소 진단 결과

**대상:** `{target_repo}`  
**상태:** `{verdict}`  
**GitHub 표시 주 언어:** `{meta['language']}`  
**검사:** {analyzed_files}개 파일 / {analyzed_bytes} bytes  
**스냅샷:** 분석 직전 GitHub API의 기본 브랜치 HEAD와 실제 checkout HEAD 일치를 확인했습니다.{receipt_line_ko}

| 확인할 항목 | 정적 신호 수 |
| --- | ---: |
{rows}

### 이 결과의 의미
- 위 숫자는 **정적 검토 신호**이며 실제 API 호출 수·오류·낭비량이 아닙니다.
- **실제 비용·토큰 절감: UNKNOWN**입니다.
- 대상 프로젝트 코드는 실행하지 않았습니다.
- 결과에 원문 코드·파일명·비밀키·API Key·비공개 저장소 내용은 포함하지 않습니다.
- 분석용 스냅샷은 이번 실행의 GitHub-hosted runner 임시 작업공간에서만 사용했습니다.

### 다음 단계
신호가 많은 경로 하나부터 같은 목표·입력·모델·품질 기준으로 Before/After 실제 사용량을 측정하세요. 비용이 줄어도 품질이나 완료율이 떨어지면 성공이 아닙니다.

[진단 요청]({issue_url}) · [GitHub Actions 실행 기록]({run_url})
"""


def write_public_output(output_dir, markdown, receipt):
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise RuntimeError("PUBLIC_OUTPUT_EXISTS")
    output_dir.mkdir(mode=0o700, parents=False)
    (output_dir / "result.md").write_text(markdown, encoding="utf-8")
    (output_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_runner_file(env_name, text):
    value = os.environ.get(env_name)
    if not value:
        raise RuntimeError("RUNNER_OUTPUT_MISSING")
    path = Path(value)
    if path.exists() and path.is_symlink():
        raise RuntimeError("RUNNER_OUTPUT_INVALID")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def friendly_error(code, lang, retry_url):
    ko = {
        "FORM_FIELD_MISSING": "입력 항목을 읽지 못했습니다. 아래 링크에서 새 요청을 만들어 주세요.",
        "FORM_CONFIRMATION_REQUIRED": "공개 진단 확인 항목에 동의해야 실행할 수 있습니다.",
        "URL_INVALID": "GitHub 저장소 주소 형식을 확인해 주세요.",
        "PUBLIC_REPO_REQUIRED": "현재 무료 공개 진단은 공개 저장소만 지원합니다.",
        "REPOSITORY_DISABLED": "비활성화된 저장소는 진단할 수 없습니다.",
        "REPO_TOO_LARGE_FOR_PUBLIC_BETA": "현재 공개 베타의 저장소 크기 한도를 초과했습니다.",
        "DEFAULT_BRANCH_MISSING": "기본 브랜치를 확인할 수 없습니다.",
        "RATE_LIMITED": f"무료 공개 베타는 사용자당 24시간에 최대 {MAX_SCANS_PER_USER_24H}회까지 실행할 수 있습니다.",
        "HEAD_MOVED_RETRY": "분석 준비 중 저장소 기본 브랜치가 변경되었습니다. 최신 상태로 다시 요청해 주세요.",
        "REPOSITORY_UNAVAILABLE": "저장소를 읽을 수 없습니다. 공개 상태와 주소를 확인해 주세요.",
        "SCAN_TIMEOUT": "안전 실행 시간 한도를 초과해 중단했습니다.",
        "SCAN_FAILED": "정적 진단 단계가 안전하게 완료되지 않아 결과를 만들지 않았습니다.",
        "BOT_NOT_ALLOWED": "자동화 계정의 공개 진단 요청은 받지 않습니다.",
    }
    en = {
        "FORM_FIELD_MISSING": "The submitted form could not be read. Please start a new request.",
        "FORM_CONFIRMATION_REQUIRED": "You must confirm the public-scan notice before the scan can run.",
        "URL_INVALID": "Please check the GitHub repository URL.",
        "PUBLIC_REPO_REQUIRED": "The free public scan currently supports public repositories only.",
        "REPOSITORY_DISABLED": "Disabled repositories cannot be scanned.",
        "REPO_TOO_LARGE_FOR_PUBLIC_BETA": "This repository exceeds the current public-beta size limit.",
        "DEFAULT_BRANCH_MISSING": "The repository default branch could not be resolved.",
        "RATE_LIMITED": f"The free public beta allows up to {MAX_SCANS_PER_USER_24H} scans per user in 24 hours.",
        "HEAD_MOVED_RETRY": "The repository default branch changed during preparation. Please submit a fresh request.",
        "REPOSITORY_UNAVAILABLE": "The repository could not be read. Check that it is public and the URL is correct.",
        "SCAN_TIMEOUT": "The scan exceeded the safe execution-time limit and was stopped.",
        "SCAN_FAILED": "The static scan did not complete safely, so no result was published.",
        "BOT_NOT_ALLOWED": "Automated accounts cannot submit public scans.",
    }
    message = (en if lang == "en" else ko).get(code)
    if not message:
        message = "The scan could not be completed safely." if lang == "en" else "진단을 안전하게 완료하지 못했습니다."
    heading = "## CostDoctor scan not completed" if lang == "en" else "## CostDoctor 진단을 완료하지 못했습니다"
    retry = "Start a new scan" if lang == "en" else "새 진단 시작"
    return f"{heading}\n\n**Status:** `{code}`\n\n{message}\n\n[{retry}]({retry_url})\n"


def main():
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    tool_sha = safe_tool_sha(os.environ.get("GITHUB_SHA", ""))
    retry_url = f"{server}/{repository}/issues/new?template=public-scan.yml"

    event = json.loads(event_path.read_text(encoding="utf-8"))
    issue = event["issue"]
    issue_number = int(issue["number"])
    issue_url = issue.get("html_url") or f"{server}/{repository}/issues/{issue_number}"
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if run_id else f"{server}/{repository}/actions"
    title = issue.get("title", "")
    body = issue.get("body") or ""
    actor = ((issue.get("user") or {}).get("login")) or os.environ.get("GITHUB_ACTOR", "")
    actor_type = ((issue.get("user") or {}).get("type")) or ""

    if not title.startswith(TITLE_PREFIX):
        return 0

    lang = parse_language(body)
    target_repo = None
    try:
        if actor_type.lower() == "bot" or actor.endswith("[bot]"):
            raise ValueError("BOT_NOT_ALLOWED")
        if not confirmation_present(body):
            raise ValueError("FORM_CONFIRMATION_REQUIRED")
        target_repo = normalize_repo(extract_field(body, URL_HEADING))
        enforce_rate_limit(repository, actor, issue_number, token)
        meta = get_target_metadata(target_repo, token)

        started = (
            f"CostDoctor가 `{target_repo}` 공개 저장소의 안전한 정적 진단을 시작했습니다. 대상 코드는 실행하지 않습니다."
            if lang == "ko"
            else f"CostDoctor started a safe static scan of public repository `{target_repo}`. Target-project code will not be executed."
        )
        post_comment(repository, issue_number, token, started)

        target_dir = runner_temp / f"costdoctor-target-{issue_number}"
        result_dir = runner_temp / f"costdoctor-result-{issue_number}"
        public_output_dir = runner_temp / f"costdoctor-public-output-{issue_number}"
        if target_dir.exists() or result_dir.exists() or public_output_dir.exists():
            raise RuntimeError("TEMP_PATH_EXISTS")

        clone_exact_snapshot(target_repo, meta["default_branch"], meta["head"], target_dir, runner_temp)

        cli = workspace / "costdoctor-entry" / "entry" / "cli.mjs"
        run(
            ["node", str(cli), "--repo", str(target_dir), "--output", str(result_dir), "--head", meta["head"]],
            timeout=120
        )
        report = load_report(result_dir)
        receipt = build_receipt(report, target_repo, meta, issue_url, run_url, tool_sha)
        markdown = format_result(report, target_repo, meta, lang, issue_url, run_url, receipt=receipt)
        write_public_output(public_output_dir, markdown, receipt)
        append_runner_file("GITHUB_STEP_SUMMARY", markdown + "\n")
        append_runner_file(
            "GITHUB_OUTPUT",
            f"public-output-dir={public_output_dir}\nreceipt-sha256={receipt['receipt_sha256']}\n"
        )
        post_comment(repository, issue_number, token, markdown)
        close_and_lock(repository, issue_number, token)
        return 0

    except urllib.error.HTTPError as e:
        code = "REPOSITORY_UNAVAILABLE" if e.code in (404, 403) else "GITHUB_API_ERROR"
    except subprocess.TimeoutExpired:
        code = "SCAN_TIMEOUT"
    except subprocess.CalledProcessError:
        code = "SCAN_FAILED"
    except ValueError as e:
        code = str(e) if re.fullmatch(r"[A-Z0-9_]+", str(e)) else "INPUT_INVALID"
    except Exception as e:
        code = str(e) if re.fullmatch(r"[A-Z0-9_]+", str(e)) else "INTERNAL_ERROR"

    try:
        post_comment(repository, issue_number, token, friendly_error(code, lang, retry_url))
        close_and_lock(repository, issue_number, token)
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
