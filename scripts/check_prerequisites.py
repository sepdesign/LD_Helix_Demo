#!/usr/bin/env python3
"""
Prerequisite check for the Helix Health Group LaunchDarkly demo.

Run this before starting the four services. It verifies that the required
toolchain is installed at the right versions, that your .env file has the
three credentials filled in, that the Python packages are available, and
which service ports are free.

    python scripts/check_prerequisites.py

Exit code 0 = every required check passed.
Exit code 1 = at least one required check failed (warnings do not fail).
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

OK, FAIL, WARN, INFO = "[ OK ]", "[FAIL]", "[WARN]", "[INFO]"
_counts = {"fail": 0, "warn": 0}


def line(tag: str, label: str, detail: str = "") -> None:
    print(f" {tag}  {label}" + (f"  ->  {detail}" if detail else ""))
    if tag == FAIL:
        _counts["fail"] += 1
    elif tag == WARN:
        _counts["warn"] += 1


def header(text: str) -> None:
    print("\n" + text)
    print("-" * len(text))


def tool_output(name: str, args: list[str]) -> str | None:
    """Return combined stdout+stderr of `name args`, or None if not installed.

    Uses shutil.which so PATHEXT resolution finds go.exe / java.exe / mvn.cmd
    on Windows. Falls back to a shell invocation for .cmd/.bat shims that
    cannot be launched directly via CreateProcess.
    """
    path = shutil.which(name)
    if not path:
        return None
    try:
        p = subprocess.run([path, *args], capture_output=True, text=True, timeout=25)
        return (p.stdout or "") + (p.stderr or "")
    except OSError:
        try:
            quoted = '"{}" {}'.format(path, " ".join(args))
            p = subprocess.run(quoted, capture_output=True, text=True, timeout=25, shell=True)
            return (p.stdout or "") + (p.stderr or "")
        except Exception:
            return None
    except subprocess.TimeoutExpired:
        return None


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        # Single-number form, e.g. java version "17"
        m2 = re.search(r'version "?(\d+)"?', text or "")
        if m2:
            return (int(m2.group(1)), 0, 0)
        return None
    return tuple(int(x) if x else 0 for x in m.groups())  # type: ignore[return-value]


def check_tool(label: str, name: str, args: list[str], minv: tuple[int, int, int],
               min_label: str, hint: str) -> None:
    out = tool_output(name, args)
    if out is None:
        line(FAIL, label, f"not found on PATH. {hint}")
        return
    v = parse_version(out)
    vs = ".".join(str(x) for x in v) if v else "unknown"
    if v is not None and v >= minv:
        line(OK, label, f"{vs}  (>= {min_label})")
    else:
        line(FAIL, label, f"{vs} found, need >= {min_label}. {hint}")


def check_python() -> None:
    v = sys.version_info[:3]
    if v >= (3, 10):
        line(OK, "Python", f"{v[0]}.{v[1]}.{v[2]}  (>= 3.10)")
    else:
        line(FAIL, "Python", f"{v[0]}.{v[1]}.{v[2]} found, need >= 3.10")


def check_env() -> None:
    header("Environment (.env)")
    if not ENV_FILE.exists():
        line(FAIL, ".env file",
             f"missing. Copy .env.example to .env and fill in your keys ({ENV_FILE})")
        return
    line(OK, ".env file", str(ENV_FILE))

    vals: dict[str, str] = {}
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, val = s.partition("=")
        vals[k.strip()] = val.strip().strip('"').strip("'")

    required = ("ANTHROPIC_API_KEY", "LD_SERVER_SDK_KEY", "LD_CLIENT_SIDE_ID")
    for key in required:
        val = vals.get(key, "")
        if not val:
            line(FAIL, key, "not set")
        elif val.endswith("...") or val in {"your-24-char-hex-id"}:
            line(FAIL, key, "still a placeholder value")
        else:
            line(OK, key, f"{val[:7]}...  ({len(val)} chars)")

    sk = vals.get("LD_SERVER_SDK_KEY", "")
    if sk and not sk.startswith("sdk-"):
        line(WARN, "LD_SERVER_SDK_KEY format",
             "a server-side key normally starts with 'sdk-' (did you paste the client-side ID?)")
    ak = vals.get("ANTHROPIC_API_KEY", "")
    if ak and not ak.startswith("sk-ant-"):
        line(WARN, "ANTHROPIC_API_KEY format", "normally starts with 'sk-ant-'")


def check_python_deps() -> None:
    header("Python packages (python-service)")
    mods = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("ldclient", "launchdarkly-server-sdk"),
        ("ldai", "launchdarkly-server-sdk-ai"),
        ("anthropic", "anthropic"),
    ]
    missing = [pkg for mod, pkg in mods if importlib.util.find_spec(mod) is None]
    if missing:
        line(WARN, "pip packages",
             "missing: " + ", ".join(missing) +
             "  (run: pip install -r python-service/requirements.txt)")
    else:
        line(OK, "pip packages", "fastapi, uvicorn, ldclient, ldai, anthropic all importable")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_ports() -> None:
    header("Service ports")
    for port, svc in ((8000, "Python"), (8001, "Go"), (8002, "Java"), (3000, "Frontend")):
        if port_in_use(port):
            line(INFO, f"port {port} ({svc})", "in use (already running, or a conflict to clear)")
        else:
            line(OK, f"port {port} ({svc})", "free")


def main() -> int:
    bar = "=" * 62
    print(bar)
    print(" Helix Health Group: LaunchDarkly demo prerequisite check")
    print(bar)

    header("Toolchain")
    check_python()
    check_tool("Go", "go", ["version"], (1, 21, 0), "1.21", "Install from https://go.dev/dl/")
    check_tool("Java", "java", ["-version"], (17, 0, 0), "17", "Install JDK 17+ from https://adoptium.net/")
    check_tool("Maven", "mvn", ["-version"], (3, 6, 0), "3.6", "Install from https://maven.apache.org/download.cgi")

    check_env()
    check_python_deps()
    check_ports()

    print("\n" + bar)
    if _counts["fail"] == 0:
        extra = f"  ({_counts['warn']} warning(s))" if _counts["warn"] else ""
        print(f" RESULT: all required checks passed{extra}")
        print(bar)
        return 0
    extra = f", {_counts['warn']} warning(s)" if _counts["warn"] else ""
    print(f" RESULT: {_counts['fail']} required check(s) FAILED{extra}")
    print(" Fix the [FAIL] items above, then re-run this check.")
    print(bar)
    return 1


if __name__ == "__main__":
    sys.exit(main())
