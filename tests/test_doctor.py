"""Тесты модуля doctor (TDD: пишем до реализации)."""

import os
import unittest

from helpers import TempDirTestCase, make_fake_jar, make_fake_tool

import doctor


class ChainDetectionTest(TempDirTestCase):
    """doctor проверяет наличие и работоспособность каждого инструмента."""

    def _sdk_layout(self, tools):
        """Собирает фейковый SDK: bin/ + build-tools/34.0.0/lib/ + platforms/android-34/.

        java по умолчанию кладётся рядом с инструментами (use_path=False в тестах),
        чтобы java не давал провала и тесты занимались только нужным инструментом.
        """
        sdk = os.path.join(self.tmpdir, "sdk")
        bindir = os.path.join(sdk, "build-tools", "34.0.0")
        os.makedirs(bindir, exist_ok=True)
        os.makedirs(os.path.join(sdk, "platforms", "android-34"), exist_ok=True)
        with open(os.path.join(sdk, "platforms", "android-34", "android.jar"), "wb") as handle:
            handle.write(b"PK\x03\x04fake")
        for name, stdout, stderr, code in tools:
            make_fake_tool(bindir, name, stdout=stdout, stderr=stderr, exit_code=code)
        if not any(name == "java" for name, _out, _err, _code in tools):
            make_fake_tool(bindir, "java", stdout='openjdk version "21.0.13" 2026-10-20')
        make_fake_jar(sdk, os.path.join("build-tools", "34.0.0", "lib", "d8.jar"))
        return sdk, bindir

    def test_reports_ok_for_complete_chain(self):
        sdk, bindir = self._sdk_layout(
            [
                ("aapt2", "Android Asset Packaging Tool (aapt) 2.20", "", 0),
                ("zipalign", "Zip alignment utility", "", 0),
                ("apksigner", "0.9", "", 0),
            ]
        )

        report = doctor.check_chain(build_tools=bindir, android_jar=None, java_bin="java", use_path=False)

        self.assertEqual(report["aapt2"]["status"], "ok")
        self.assertEqual(report["aapt2"]["version"], "2.20")
        self.assertEqual(report["zipalign"]["status"], "ok")
        self.assertEqual(report["apksigner"]["status"], "ok")
        self.assertEqual(report["apksigner"]["version"], "0.9")
        self.assertEqual(report["d8"]["status"], "ok")

    def test_absent_zipalign_is_warning_not_failure(self):
        """zipalign необязателен: его отсутствие = warning, сборка не падает."""
        sdk, bindir = self._sdk_layout(
            [
                ("aapt2", "Android Asset Packaging Tool (aapt) 2.20", "", 0),
                ("apksigner", "0.9", "", 0),
            ]
        )

        report = doctor.check_chain(
            build_tools=bindir, android_jar=None, java_bin="java", use_path=False
        )

        self.assertEqual(report["zipalign"]["status"], "absent")
        self.assertIn("zipalign", report["zipalign"]["hint"])
        self.assertFalse(doctor.has_failures(report))

    def test_reports_crash_as_broken(self):
        """Бинарник есть, но падает при --version — это broken, а не ok."""
        sdk, bindir = self._sdk_layout(
            [
                ("aapt2", "Android Asset Packaging Tool (aapt) 2.20", "", 0),
                ("zipalign", "Zip alignment utility", "", 0),
                ("apksigner", "", "java.lang.UnsatisfiedLinkError", 1),
            ]
        )

        report = doctor.check_chain(build_tools=bindir, android_jar=None, java_bin="java", use_path=False)

        self.assertEqual(report["apksigner"]["status"], "broken")

    def test_kotlinc_missing_is_warning_not_failure(self):
        """kotlinc не обязателен для java-проектов — попадает в warnings."""
        sdk, bindir = self._sdk_layout(
            [
                ("aapt2", "Android Asset Packaging Tool (aapt) 2.20", "", 0),
                ("zipalign", "Zip alignment utility", "", 0),
                ("apksigner", "0.9", "", 0),
            ]
        )

        report = doctor.check_chain(
            build_tools=bindir,
            android_jar=None,
            java_bin="java",
            kotlinc=None,
            use_path=False,
        )

        self.assertEqual(report["kotlinc"]["status"], "missing")
        self.assertFalse(doctor.has_failures(report))

    def test_d8_jar_missing_is_failure(self):
        sdk, bindir = self._sdk_layout(
            [
                ("aapt2", "Android Asset Packaging Tool (aapt) 2.20", "", 0),
                ("zipalign", "Zip alignment utility", "", 0),
                ("apksigner", "0.9", "", 0),
            ]
        )
        os.unlink(os.path.join(bindir, "lib", "d8.jar"))

        report = doctor.check_chain(build_tools=bindir, android_jar=None, java_bin="java", use_path=False)

        self.assertEqual(report["d8"]["status"], "missing")
        self.assertTrue(doctor.has_failures(report, extra_required=["d8"]))


class DiscoverDoctorTest(TempDirTestCase):
    """doctor должен сам находить SDK в типичных местах и объяснять, что ставить."""

    def test_needs_sdk_help_when_android_jar_missing(self):
        report = {
            "aapt2": {"status": "ok"},
            "d8": {"status": "ok"},
            "android_jar": {"status": "missing"},
            "apksigner": {"status": "ok"},
        }

        self.assertTrue(doctor.needs_sdk_help(report))

    def test_no_help_needed_when_everything_ok(self):
        report = {
            "aapt2": {"status": "ok"},
            "d8": {"status": "ok"},
            "android_jar": {"status": "ok"},
            "apksigner": {"status": "ok"},
        }

        self.assertFalse(doctor.needs_sdk_help(report))

    def test_format_report_contains_install_hint_for_missing_sdk(self):
        report = doctor.check_chain(
            build_tools=None, android_jar=None, java_bin="java", use_path=False, discover=False
        )

        text = doctor.format_report(report)

        self.assertIn("pkg install openjdk-21 android-sdk", text)
        self.assertIn("ANDROID_HOME", text)

    def test_discover_finds_build_tools_from_home(self):
        """Кладём фейковый SDK в типичное место и проверяем, что discover его нашёл."""
        import env

        sdk = os.path.join(self.tmpdir, "android-sdk")
        bt = os.path.join(sdk, "build-tools", "34.0.0")
        os.makedirs(os.path.join(bt, "lib"))
        with open(os.path.join(bt, "lib", "d8.jar"), "wb") as handle:
            handle.write(b"PK")

        found = env.discover_build_tools(extra_roots=[sdk])

        self.assertIn(bt, found)
    def test_has_failures_ignores_warnings(self):
        report = {
            "aapt2": {"status": "ok"},
            "zipalign": {"status": "warning", "hint": "no zipalign"},
            "kotlinc": {"status": "missing", "hint": "nope"},
        }
        self.assertFalse(doctor.has_failures(report))

    def test_has_failures_flags_broken(self):
        report = {
            "aapt2": {"status": "ok"},
            "apksigner": {"status": "broken", "hint": "crashes"},
            "zipalign": {"status": "warning"},
            "kotlinc": {"status": "missing"},
        }
        self.assertTrue(doctor.has_failures(report))


if __name__ == "__main__":
    unittest.main()