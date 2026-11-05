#!/usr/bin/env python3
"""Прогнать тесты: python3 tests/run.py"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(os.path.dirname(TESTS_DIR), "lib")

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)


def main():
    suite = unittest.defaultTestLoader.discover(TESTS_DIR, pattern="test_*.py")
    # Часть тестов намеренно проверяет печать ошибок — глушим stdout,
    # чтобы отчёт не путался с ожидаемым выводом.
    with redirect_stdout(io.StringIO()):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())