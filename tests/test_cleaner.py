"""Тесты очистки."""

import os
import unittest

from helpers import TempDirTestCase

import cleaner


class CleanTest(TempDirTestCase):
    def test_removes_build_dir(self):
        build = os.path.join(self.tmpdir, "build", ".tmp", "dex")
        os.makedirs(build)
        with open(os.path.join(build, "classes.dex"), "w", encoding="utf-8") as handle:
            handle.write("x")

        removed = cleaner.clean(self.tmpdir)

        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "build")))
        self.assertTrue(removed)

    def test_removes_debug_keystore(self):
        path = os.path.join(self.tmpdir, ".debug.keystore")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("keys")

        cleaner.clean(self.tmpdir)

        self.assertFalse(os.path.exists(path))

    def test_keeps_sources_and_explicit_keystore(self):
        src = os.path.join(self.tmpdir, "src", "Main.java")
        os.makedirs(os.path.dirname(src))
        with open(src, "w", encoding="utf-8") as handle:
            handle.write("class Main {}")
        keystore = os.path.join(self.tmpdir, "release.keystore")
        with open(keystore, "w", encoding="utf-8") as handle:
            handle.write("keys")

        cleaner.clean(self.tmpdir)

        self.assertTrue(os.path.exists(src))
        self.assertTrue(os.path.exists(keystore))

    def test_nothing_to_clean_is_not_an_error(self):
        self.assertEqual(cleaner.clean(self.tmpdir), [])


if __name__ == "__main__":
    unittest.main()