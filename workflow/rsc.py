#!/usr/bin/python3
"""Alfred Script Filter for Raycast script commands.

Keyword rsc lists commands discovered from script_dirs. Inline commands show
a cached first line and refresh in the background. Return on an inline row
refreshes now and reopens Alfred on rsc. Other modes run the script.
"""
import base64
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

BUNDLE = "com.aliafshany.raycast-script-commands"
FALLBACK_CACHE = (
    "~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/" + BUNDLE
)
LOCK_MAX_AGE = 45
RUN_TIMEOUT = 30
HEADER_RE = re.compile(r"^\s*(?:#|//)\s*@raycast\.([A-Za-z0-9_.-]+)\s*(.*?)\s*$")
ANSI_RE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"
    r"|\x1b[@-_]"
)
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}


def cache_dir():
    raw = os.environ.get("alfred_workflow_cache")
    if raw:
        return Path(raw)
    return Path(FALLBACK_CACHE).expanduser()


def cache_key(path):
    real = os.path.realpath(path)
    return hashlib.sha256(real.encode("utf-8")).hexdigest()[:16]


def cache_path(key):
    return cache_dir() / f"{key}.json"


def lock_path(key):
    return cache_dir() / f"{key}.lock"


def read_cache(key):
    try:
        data = json.loads(cache_path(key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def write_cache(key, data):
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{key}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, cache_path(key))


def lock_age(key):
    try:
        return time.time() - lock_path(key).stat().st_mtime
    except OSError:
        return None


def lock_exists(key):
    return lock_path(key).exists()


def acquire_lock(key):
    cache_dir().mkdir(parents=True, exist_ok=True)
    path = lock_path(key)
    for _ in range(3):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            age = lock_age(key)
            if age is not None and age < LOCK_MAX_AGE:
                return False
            try:
                path.unlink()
            except OSError:
                return False
            continue
        else:
            try:
                os.write(fd, f"{time.time()}\n".encode())
            finally:
                os.close(fd)
            return True
    return False


def release_lock(key):
    try:
        lock_path(key).unlink()
    except OSError:
        pass


def script_dirs():
    raw = os.environ.get("script_dirs") or "~/raycast-scripts"
    folders = []
    for part in raw.split(":"):
        part = part.strip()
        if part:
            folders.append(os.path.expanduser(part))
    return folders


def parse_ttl(raw):
    if not raw:
        return 60
    matched = re.fullmatch(r"(\d+)\s*([smhd])?", raw.strip().lower())
    if not matched:
        return 60
    amount = int(matched.group(1))
    unit = matched.group(2) or "s"
    scale = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return max(1, amount * scale)


def needs_argument(headers):
    for key in headers:
        head = key.split(".", 1)[0]
        if head.startswith("argument") and len(head) > 8 and head[8].isdigit():
            return True
    return False


def emoji_icon(value):
    if not value or "/" in value or "\\" in value:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_ .:*-]+", value):
        return ""
    return value


def read_headers(path):
    try:
        with open(path, "rb") as handle:
            blob = handle.read(65536)
    except OSError:
        return {}
    headers = {}
    for line in blob.decode("utf-8", "replace").splitlines():
        matched = HEADER_RE.match(line)
        if matched:
            headers[matched.group(1)] = matched.group(2).strip()
    return headers


def discover():
    found = []
    seen = set()
    for folder in script_dirs():
        if not os.path.isdir(folder):
            continue
        for root, dirs, files in os.walk(folder):
            dirs[:] = [name for name in dirs if not name.startswith(".") and name not in SKIP_DIRS]
            for name in files:
                if name.startswith("."):
                    continue
                path = os.path.join(root, name)
                real = os.path.realpath(path)
                if real in seen or not os.path.isfile(real):
                    continue
                headers = read_headers(real)
                title = headers.get("title") or ""
                mode = headers.get("mode") or ""
                if not title or not mode:
                    continue
                seen.add(real)
                found.append({
                    "path": real,
                    "key": cache_key(real),
                    "title": title,
                    "mode": mode,
                    "ttl": parse_ttl(headers.get("refreshTime")),
                    "package": headers.get("packageName") or "",
                    "icon": emoji_icon(headers.get("icon") or ""),
                    "unsupported": needs_argument(headers) or mode not in {"inline", "silent", "compact", "fullOutput"},
                    "bad_mode": mode not in {"inline", "silent", "compact", "fullOutput"},
                })
    found.sort(key=lambda entry: (entry["title"].casefold(), entry["path"]))
    return found


def script_env():
    env = os.environ.copy()
    rest = [
        part for part in env.get("PATH", "").split(":")
        if part and part not in ("/opt/homebrew/bin", "/usr/local/bin")
    ]
    if not rest:
        rest = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    env["PATH"] = ":".join(["/opt/homebrew/bin", "/usr/local/bin"] + rest)
    env.setdefault("LANG", "en_US.UTF-8")
    return env


def command_for(path):
    if os.access(path, os.X_OK):
        return [path]
    try:
        with open(path, "rb") as handle:
            first = handle.readline(256)
    except OSError:
        return [path]
    if first.startswith(b"#!"):
        parts = first[2:].decode("utf-8", "replace").strip().split()
        if parts:
            return parts + [path]
    return [path]


def clean_text(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    text = ANSI_RE.sub("", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def nonempty_lines(text):
    return [line.strip() for line in clean_text(text).splitlines() if line.strip()]


def first_line(text):
    lines = nonempty_lines(text)
    return lines[0] if lines else ""


def last_line(text):
    lines = nonempty_lines(text)
    return lines[-1] if lines else ""


def short(text):
    text = " ".join(clean_text(text).split())
    if len(text) > 80:
        return text[:79] + "…"
    return text


def failed(prev_value, err):
    return {"value": prev_value, "ts": time.time(), "ok": False, "err": short(err), "full": ""}


def run_command(path, previous_value=""):
    try:
        proc = subprocess.Popen(
            command_for(path),
            cwd=str(Path(path).resolve().parent),
            env=script_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return failed(previous_value, exc.strerror or str(exc))
    try:
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return failed(previous_value, "timeout")
    stdout = stdout or ""
    stderr = stderr or ""
    full = clean_text(stdout).strip()
    if proc.returncode != 0:
        detail = first_line(stderr) or first_line(stdout)
        err = f"exit {proc.returncode}"
        if detail:
            err = f"{err}: {detail}"
        record = failed(previous_value, err)
        record["full"] = full
        return record
    value = first_line(stdout)
    if not value:
        record = failed(previous_value, first_line(stderr) or "empty output")
        record["full"] = full
        return record
    if len(full) > 8000:
        full = full[:8000] + "…"
    return {"value": value, "ts": time.time(), "ok": True, "err": "", "full": full}


def cache_record(result):
    return {
        "value": result.get("value") if isinstance(result.get("value"), str) else "",
        "ts": result.get("ts"),
        "ok": result.get("ok"),
        "err": result.get("err") or "",
    }


def spawn_refresh(path, key):
    if not acquire_lock(key):
        return
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--refresh", path],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError:
        release_lock(key)


def cache_is_fresh(entry, cache):
    if not cache:
        return False
    ts = cache.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return False
    return (time.time() - float(ts)) <= entry["ttl"]


def ensure_fresh(entry, cache):
    if entry["unsupported"] or entry["mode"] != "inline":
        return
    if cache_is_fresh(entry, cache):
        return
    age = lock_age(entry["key"])
    if age is not None and age < LOCK_MAX_AGE:
        return
    spawn_refresh(entry["path"], entry["key"])


def store_refresh(path):
    key = cache_key(path)
    previous = read_cache(key) or {}
    previous_value = previous.get("value") if isinstance(previous.get("value"), str) else ""
    write_cache(key, cache_record(run_command(path, previous_value)))


def refresh_child(path):
    try:
        store_refresh(path)
    finally:
        release_lock(cache_key(path))


def encode_path(path):
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")


def decode_path(token):
    pad = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + pad).decode("utf-8")


def format_age(ts):
    delta = max(0, int(time.time() - float(ts)))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    return f"{delta // 3600}h"


def inline_subtitle(entry, cache, refreshing):
    bits = [entry["title"]]
    ts = cache.get("ts") if cache else None
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        bits.append(f"updated {format_age(ts)} ago")
    if refreshing:
        bits.append("refreshing")
    if cache and cache.get("ok") is False:
        bits.append("⚠ " + (cache.get("err") or "error"))
    if len(bits) == 1:
        bits.append("refreshing")
    return " · ".join(bits)


def filter_item(entry, cache, refreshing):
    prefix = f"{entry['icon']} " if entry["icon"] else ""
    variables = {"rsc_mode": entry["mode"], "rsc_title": entry["title"]}
    if entry["bad_mode"]:
        return {
            "uid": entry["key"],
            "title": prefix + entry["title"],
            "subtitle": f"unsupported mode {entry['mode']}",
            "match": entry["title"],
            "valid": False,
        }
    if entry["unsupported"]:
        return {
            "uid": entry["key"],
            "title": prefix + entry["title"],
            "subtitle": "needs an argument · not supported yet",
            "match": entry["title"],
            "valid": False,
        }
    if entry["mode"] == "inline":
        value = cache.get("value") if cache and isinstance(cache.get("value"), str) else ""
        if value:
            title = prefix + value
        elif cache and cache.get("ok") is False:
            title = prefix + "—"
        else:
            title = prefix + "Loading…"
        return {
            "uid": entry["key"],
            "title": title,
            "subtitle": inline_subtitle(entry, cache, refreshing),
            "match": entry["title"],
            "arg": "refresh:" + encode_path(entry["path"]),
            "valid": True,
            "text": {"copy": value, "largetype": value},
            "variables": variables,
        }
    label = "full output" if entry["mode"] == "fullOutput" else entry["mode"]
    bits = [label]
    if entry["package"]:
        bits.append(entry["package"])
    return {
        "uid": entry["key"],
        "title": prefix + entry["title"],
        "subtitle": " · ".join(bits),
        "match": entry["title"],
        "arg": f"run:{entry['mode']}:" + encode_path(entry["path"]),
        "valid": True,
        "variables": variables,
    }


def emit_filter():
    entries = discover()
    items = []
    any_inline = False
    for entry in entries:
        cache = None
        refreshing = False
        if entry["mode"] == "inline" and not entry["unsupported"] and not entry["bad_mode"]:
            any_inline = True
            cache = read_cache(entry["key"])
            ensure_fresh(entry, cache)
            refreshing = lock_exists(entry["key"])
        items.append(filter_item(entry, cache, refreshing))
    if not items:
        shown = os.environ.get("script_dirs") or "~/raycast-scripts"
        items = [{"title": "No script commands found", "subtitle": shown, "valid": False}]
    payload = {"skipknowledge": True, "items": items}
    if any_inline:
        payload["rerun"] = 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def reopen_rsc():
    # Alfred closes when this action finishes. Reopen after that, once the cache is fresh.
    subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time,subprocess; time.sleep(0.4); "
            "subprocess.run(['osascript','-e',"
            "'tell application id \"com.runningwithcrayons.Alfred\" to search \"rsc\"'])",
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def run_action(arg):
    kind, _, rest = (arg or "").partition(":")
    if kind == "refresh":
        store_refresh(decode_path(rest))
        reopen_rsc()
        return 0
    if kind == "run":
        mode, _, token = rest.partition(":")
        result = run_command(decode_path(token))
        if mode == "fullOutput":
            text = result.get("full") or result.get("err") or "(no output)"
        else:
            text = last_line(result.get("full") or "") or result.get("err") or "(no output)"
        print(text)
        return 0
    print("(unknown action)")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "--refresh":
        if len(argv) < 3:
            print("usage: rsc.py --refresh <path>", file=sys.stderr)
            return 2
        refresh_child(argv[2])
        return 0
    if len(argv) >= 2 and argv[1] == "--run":
        return run_action(argv[2] if len(argv) > 2 else "")
    return emit_filter()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
