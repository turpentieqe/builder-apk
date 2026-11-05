"""Тесты генератора скелета проекта."""

import os
import unittest

from helpers import TempDirTestCase

import init_template


class ScaffoldTest(TempDirTestCase):
    def _scaffold(self, **kwargs):
        params = {
            "directory": os.path.join(self.tmpdir, "app"),
            "name": "TestApp",
            "package": "com.example.testapp",
            "lang": "kotlin",
        }
        params.update(kwargs)
        return init_template.scaffold(**params)

    def test_kotlin_project_has_all_files(self):
        created = self._scaffold(lang="kotlin")
        names = {os.path.basename(path) for path in created}

        self.assertIn("AndroidManifest.xml", names)
        self.assertIn("MainActivity.kt", names)
        self.assertIn("strings.xml", names)
        self.assertIn(".gitignore", names)
        self.assertIn("README.md", names)

    def test_java_project_creates_java_file(self):
        created = self._scaffold(lang="java")
        names = {os.path.basename(path) for path in created}

        self.assertIn("MainActivity.java", names)
        self.assertNotIn("MainActivity.kt", names)

    def test_manifest_contains_package_and_label(self):
        created = self._scaffold()
        manifest = [p for p in created if p.endswith("AndroidManifest.xml")][0]
        with open(manifest, encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn('package="com.example.testapp"', content)
        self.assertIn('android:label="TestApp"', content)
        self.assertIn("android.intent.action.MAIN", content)

    def test_java_class_uses_package(self):
        created = self._scaffold(lang="java")
        source = [p for p in created if p.endswith("MainActivity.java")][0]
        with open(source, encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("package com.example.testapp;", content)
        self.assertIn("class MainActivity extends Activity", content)

    def test_java_class_filename_is_not_kotlin_syntax(self):
        """Java-версия не должна содержать Kotlin-специфику (override fun)."""
        created = self._scaffold(lang="java")
        source = [p for p in created if p.endswith("MainActivity.java")][0]
        with open(source, encoding="utf-8") as handle:
            content = handle.read()

        self.assertNotIn("override fun", content)
        self.assertIn("@Override", content)

    def test_non_empty_directory_without_force_fails(self):
        directory = os.path.join(self.tmpdir, "busy")
        os.makedirs(directory)
        with open(os.path.join(directory, "keep.txt"), "w", encoding="utf-8") as handle:
            handle.write("x")

        with self.assertRaises(SystemExit):
            self._scaffold(directory=directory)

    def test_force_allows_overwrite(self):
        directory = os.path.join(self.tmpdir, "busy")
        os.makedirs(directory)
        with open(os.path.join(directory, "keep.txt"), "w", encoding="utf-8") as handle:
            handle.write("x")

        created = self._scaffold(directory=directory, force=True)
        self.assertTrue(created)

    def test_invalid_lang_is_rejected(self):
        with self.assertRaises(SystemExit):
            self._scaffold(lang="rust")

    def test_gitignore_excludes_build_and_keystore(self):
        created = self._scaffold()
        path = [p for p in created if p.endswith(".gitignore")][0]
        with open(path, encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("build/", content)
        self.assertIn("*.keystore", content)


if __name__ == "__main__":
    unittest.main()