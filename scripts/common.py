#!/usr/bin/env python3
"""Shared helpers for the TWN auto-video pipeline."""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def log(*a):
    print("[twn]", *a, flush=True)


def run(cmd, timeout=300, **kw):
    log("$", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, timeout=timeout, **kw)


def dur_of(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path]
    ).decode().strip()
    return float(out)
