"""Тесты инспектора APK (парсинг вывода, без SDK)."""

import unittest

from helpers import TempDirTestCase

import inspector

BADGING_SAMPLE = """package: name='com.dragonnest.game' versionCode='1' versionName='1.0' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'
sdkVersion:'21'
targetSdkVersion:'34'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.VIBRATE'
application-label:'Гнездо Дракона'
application-label-ru:'Гнездо Дракона'
application-icon-160:'res/mipmap-mdpi-v4/ic_launcher.png'
launchable-activity: name='com.dragonnest.game.MainActivity'  label='' icon=''
"""

CERTS_SAMPLE = """Verifies
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=Dragon Nest, O=Home
Signer #1 certificate SHA-256 digest: b49124e35b0304e79dd5ce26e49f8fb18d84971aa6270ad93b6326f8daca9215
"""


class ParseBadgingTest(unittest.TestCase):
    def test_extracts_core_fields(self):
        data = inspector.parse_badging(BADGING_SAMPLE)

        self.assertEqual(data["package"], "com.dragonnest.game")
        self.assertEqual(data["version_code"], "1")
        self.assertEqual(data["version_name"], "1.0")
        self.assertEqual(data["sdk_version"], "21")
        self.assertEqual(data["target_sdk"], "34")
        self.assertEqual(data["launchable"], "com.dragonnest.game.MainActivity")

    def test_collects_permissions(self):
        data = inspector.parse_badging(BADGING_SAMPLE)

        self.assertEqual(
            data["permissions"],
            ["android.permission.INTERNET", "android.permission.VIBRATE"],
        )

    def test_label_does_not_get_overwritten_by_locale_variant(self):
        data = inspector.parse_badging(BADGING_SAMPLE)

        self.assertEqual(data["label"], "Гнездо Дракона")

    def test_empty_input_is_safe(self):
        data = inspector.parse_badging("")

        self.assertIsNone(data["package"])
        self.assertEqual(data["permissions"], [])


class ParseCertsTest(unittest.TestCase):
    def test_detects_schemes_and_dn(self):
        info = inspector.parse_certs(CERTS_SAMPLE)

        self.assertTrue(info["signed"])
        self.assertEqual(info["schemes"], ["v1", "v2", "v3"])
        self.assertEqual(info["dn"], "CN=Dragon Nest, O=Home")
        self.assertTrue(info["sha256"].startswith("b49124e"))

    def test_unsigned_is_not_signed(self):
        info = inspector.parse_certs("DOES NOT VERIFY\nERROR: Missing AndroidManifest.xml")

        self.assertFalse(info["signed"])

    def test_termux_apksigner_format_is_understood(self):
        """Termux-сборка apksigner печатает 'V3.0 Signer: certificate DN: …' без строк Verified using."""
        text = (
            "V3.0 Signer: certificate DN: CN=builder-apk, O=Debug\n"
            "V3.0 Signer: certificate SHA-256 digest: d8907bd11218b7add3672fe967168c86063c6c594c9d069ab3685585bed62db4\n"
        )
        info = inspector.parse_certs(text)

        self.assertTrue(info["signed"])
        self.assertEqual(info["dn"], "CN=builder-apk, O=Debug")
        self.assertTrue(info["sha256"].startswith("d8907bd"))


class HumanSizeTest(unittest.TestCase):
    def test_formats_bytes_and_mib(self):
        self.assertEqual(inspector.human_size(512), "512 B")
        self.assertEqual(inspector.human_size(2048), "2.0 KiB")
        self.assertEqual(inspector.human_size(5 * 1024 * 1024), "5.0 MiB")


class InspectMissingFileTest(TempDirTestCase):
    def test_missing_file_reports_error(self):
        data = inspector.inspect(self.tmpdir + "/nope.apk")

        self.assertFalse(data["exists"])
        self.assertTrue(data["errors"])


if __name__ == "__main__":
    unittest.main()