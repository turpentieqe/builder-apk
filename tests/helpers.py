"""Общие хелперы для тестов builder-apk.

Фейковые инструменты: создаём исполняемые shell-скрипты в tmp-директории,
которые на любой вызов печатают заданный вывод. Так тесты не зависят от
реально установленного Android SDK.
"""

import os
import stat
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(REPO_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


def make_fake_tool(directory, name, stdout="", stderr="", exit_code=0):
    """Создаёт исполняемый скрипт-заглушку и возвращает его путь."""
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n")
        if stdout:
            handle.write("cat <<'FAKE_EOF'\n%s\nFAKE_EOF\n" % stdout.rstrip("\n"))
        if stderr:
            handle.write("cat >&2 <<'FAKE_EOF'\n%s\nFAKE_EOF\n" % stderr.rstrip("\n"))
        handle.write("exit %d\n" % exit_code)
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def make_fake_jar(directory, relpath):
    """Создаёт пустой файл, изображающий jar, и возвращает путь."""
    path = os.path.join(directory, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"PK\x03\x04fake")
    return path


class TempDirTestCase(unittest.TestCase):
    """Тест-кейс с автоматической временной директорией."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()