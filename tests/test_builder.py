"""Тесты сборщика: разбор стадий, предупреждения, ошибки."""

import os
import unittest

from helpers import TempDirTestCase, make_fake_tool

import builder


class ScanStderrTest(unittest.TestCase):
    def test_detects_jansi_noise(self):
        stderr = (
            "Failed to load native library:jansi-2.4.0-libjansi.so. osinfo: Linux/arm64\n"
            "java.lang.UnsatisfiedLinkError: dlopen failed"
        )
        warnings = builder.scan_stderr("compile", stderr)

        messages = " ".join(w["message"] for w in warnings)
        self.assertIn("jansi", messages)

    def test_clean_stderr_has_no_warnings(self):
        self.assertEqual(builder.scan_stderr("compile", ""), [])

    def test_jansi_does_not_duplicate_unsatisfiedlink_warning(self):
        stderr = (
            "Failed to load native library:jansi-2.4.0-libjansi.so. osinfo: Linux/arm64\n"
            "java.lang.UnsatisfiedLinkError: dlopen failed: library libc.so.6 not found"
        )
        warnings = builder.scan_stderr("compile", stderr)

        self.assertEqual(len(warnings), 1)
        self.assertIn("jansi", warnings[0]["message"])

    def test_warning_carries_stage(self):
        warnings = builder.scan_stderr("kotlinc", "jansi boom")

        self.assertEqual(warnings[0]["stage"], "kotlinc")


class DetectLangTest(TempDirTestCase):
    def test_detects_kotlin(self):
        src = os.path.join(self.tmpdir, "src", "com", "x")
        os.makedirs(src)
        with open(os.path.join(src, "Main.kt"), "w", encoding="utf-8") as handle:
            handle.write("class Main")

        lang, sources = builder.detect_lang(self.tmpdir)

        self.assertEqual(lang, "kotlin")
        self.assertEqual(len(sources), 1)

    def test_detects_java(self):
        src = os.path.join(self.tmpdir, "src")
        os.makedirs(src)
        with open(os.path.join(src, "Main.java"), "w", encoding="utf-8") as handle:
            handle.write("class Main {}")

        lang, sources = builder.detect_lang(self.tmpdir)

        self.assertEqual(lang, "java")

    def test_kotlin_wins_when_both_present(self):
        src = os.path.join(self.tmpdir, "src")
        os.makedirs(src)
        for name in ("A.kt", "B.java"):
            with open(os.path.join(src, name), "w", encoding="utf-8") as handle:
                handle.write("x")

        lang, _sources = builder.detect_lang(self.tmpdir)

        self.assertEqual(lang, "kotlin")

    def test_no_sources_returns_none(self):
        lang, sources = builder.detect_lang(self.tmpdir)

        self.assertIsNone(lang)
        self.assertEqual(sources, [])


class CommandBuildersTest(unittest.TestCase):
    def test_kotlin_command_includes_classpath_and_sources(self):
        cmd = builder._compile_kotlin("kotlinc", "/sdk/android.jar", "/out", ["/src/A.kt"])

        self.assertEqual(cmd[0], "kotlinc")
        self.assertIn("-classpath", cmd)
        self.assertIn("/sdk/android.jar", cmd)
        self.assertIn("/src/A.kt", cmd)

    def test_java_command_uses_bootclasspath(self):
        cmd = builder._compile_java("/sdk/android.jar", "/out", ["/src/A.java"])

        self.assertEqual(cmd[0], "javac")
        self.assertIn("-bootclasspath", cmd)
        self.assertIn("/sdk/android.jar", cmd)

    def test_d8_command_min_api_and_output(self):
        cmd = builder._d8_cmd(
            "java", "/bt/lib/d8.jar", "/sdk/android.jar", 21, "/dex", ["/c/A.class"]
        )

        self.assertIn("com.android.tools.r8.D8", cmd)
        self.assertIn("--min-api", cmd)
        self.assertIn("21", cmd)
        self.assertIn("--output", cmd)
        self.assertIn("/c/A.class", cmd)


class ResolveSdkTest(TempDirTestCase):
    def test_missing_sdk_raises(self):
        with self.assertRaises(builder.BuildError):
            builder.resolve_sdk(sdk=None, build_tools=None)

    def test_explicit_build_tools_is_used(self):
        bt = os.path.join(self.tmpdir, "build-tools", "34.0.0")
        os.makedirs(bt)

        self.assertEqual(builder.resolve_sdk(build_tools=bt), bt)

    def test_missing_android_jar_raises(self):
        with self.assertRaises(builder.BuildError):
            builder.resolve_android_jar(android_jar="/nope/android.jar")


class StatSizeTest(TempDirTestCase):
    def test_existing_file(self):
        path = os.path.join(self.tmpdir, "f.bin")
        with open(path, "wb") as handle:
            handle.write(b"12345")

        self.assertEqual(builder.stat_size(path), 5)

    def test_missing_file_is_none(self):
        self.assertIsNone(builder.stat_size(os.path.join(self.tmpdir, "nope")))


class BuildErrorTest(TempDirTestCase):
    def test_missing_manifest_fails_fast(self):
        code = builder.build(project_dir=self.tmpdir, build_tools=self.tmpdir)

        self.assertEqual(code, 1)

    def test_run_reports_missing_command(self):
        with self.assertRaises(builder.BuildError) as ctx:
            builder._run([os.path.join(self.tmpdir, "absent-binary")], "test")

        self.assertEqual(ctx.exception.stage, "test")
        self.assertIn("не найдена", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()