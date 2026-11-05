#!/usr/bin/env python3
"""Makefile-подобный запуск на случай, если нет make."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "help"
    if target == "test":
        return run([sys.executable, os.path.join("tests", "run.py")])
    if target == "doctor":
        return run([os.path.join("bin", "builder-apk"), "doctor"])
    if target == "help":
        print("Доступно: test, doctor")
        return 0
    print("неизвестная цель: %s" % target, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())