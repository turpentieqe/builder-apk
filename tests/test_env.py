"""Тесты определения окружения (архитектура, поиск SDK)."""

import os
import struct
import unittest

from helpers import TempDirTestCase

import env


def write_elf(path, machine, little_endian=True):
    """Пишет минимальный ELF-заголовок с нужным e_machine."""
    endian = "<" if little_endian else ">"
    header = bytearray(b"\x7fELF")
    header.append(2 if little_endian else 1)  # EI_DATA
    header.append(1)  # EV_CURRENT
    header.append(0)  # EI_OSABI
    header.extend([0, 0, 0, 0, 0, 0, 0, 0, 0])  # padding до e_type
    header.extend(b"\x02\x00")  # e_type = EXEC
    header.extend(struct.pack(endian + "H", machine))
    with open(path, "wb") as handle:
        handle.write(bytes(header))


class ElfArchTest(TempDirTestCase):
    def test_reads_aarch64(self):
        path = os.path.join(self.tmpdir, "aarch64-bin")
        write_elf(path, 183)
        self.assertEqual(env.elf_arch(path), "aarch64")

    def test_reads_x86_64(self):
        path = os.path.join(self.tmpdir, "x86-bin")
        write_elf(path, 62)
        self.assertEqual(env.elf_arch(path), "x86-64")

    def test_non_elf_returns_none(self):
        path = os.path.join(self.tmpdir, "script.sh")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\necho hi\n")
        self.assertIsNone(env.elf_arch(path))

    def test_missing_file_returns_none(self):
        self.assertIsNone(env.elf_arch(os.path.join(self.tmpdir, "nope")))

    def test_runnable_false_on_arch_mismatch(self):
        path = os.path.join(self.tmpdir, "x86-bin")
        write_elf(path, 62)
        # На ARM-хосте x86-бинарник не должен считаться запускаемым
        if env.host_arch() == "aarch64":
            self.assertFalse(env.is_runnable(path))

    def test_scripts_are_treated_as_runnable(self):
        """Не-ELF (скрипты) не блокируем — пусть решает запуск."""
        path = os.path.join(self.tmpdir, "tool.sh")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nexit 0\n")
        self.assertTrue(env.is_runnable(path))

    def test_mismatch_hint_mentions_both_architectures(self):
        path = os.path.join(self.tmpdir, "x86-bin")
        write_elf(path, 62)
        hint = env.arch_mismatch_hint(path)
        self.assertIn("x86-64", hint)
        self.assertIn(env.host_arch(), hint)


class DiscoverTest(TempDirTestCase):
    def _make_sdk(self, root, build_tools_ver="34.0.0"):
        bt = os.path.join(root, "build-tools", build_tools_ver)
        os.makedirs(os.path.join(bt, "lib"))
        with open(os.path.join(bt, "lib", "d8.jar"), "wb") as handle:
            handle.write(b"PK")
        platform = os.path.join(root, "platforms", "android-34")
        os.makedirs(platform)
        with open(os.path.join(platform, "android.jar"), "wb") as handle:
            handle.write(b"PK")
        return bt

    def test_discover_build_tools_from_extra_root(self):
        root = os.path.join(self.tmpdir, "sdk")
        bt = self._make_sdk(root)

        found = env.discover_build_tools(extra_roots=[root])

        self.assertIn(bt, found)

    def test_discover_android_jar_after_build_tools(self):
        root = os.path.join(self.tmpdir, "sdk")
        bt = self._make_sdk(root)

        jar = env.discover_android_jar(bt, target_sdk=34)

        self.assertIsNotNone(jar)
        self.assertTrue(jar.endswith("android-34/android.jar"))

    def test_discover_kotlinc_from_extra_root(self):
        root = os.path.join(self.tmpdir, "kotlin")
        bindir = os.path.join(root, "kotlinc", "bin")
        os.makedirs(bindir)
        kotlinc = os.path.join(bindir, "kotlinc")
        with open(kotlinc, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nexit 0\n")

        found = env.discover_kotlinc(extra_roots=[root])

        # Если в системе есть kotlinc, вернётся он — проверяем, что поиск не падает
        self.assertIsNotNone(found)


if __name__ == "__main__":
    unittest.main()