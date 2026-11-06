"""Тесты реестра языков."""

import unittest

from helpers import REPO_ROOT  # noqa: F401  (кладёт lib/ в sys.path)

import languages


class RegistryTest(unittest.TestCase):
    def test_expected_languages_are_registered(self):
        self.assertEqual(set(languages.ALL_LANGUAGES), {"kotlin", "java", "groovy", "scala"})

    def test_each_language_has_extension(self):
        for lang in languages.ALL_LANGUAGES:
            with self.subTest(lang=lang):
                self.assertTrue(languages.extension_for(lang).startswith("."))

    def test_reverse_lookup(self):
        self.assertEqual(languages.lang_for_extension(".kt"), "kotlin")
        self.assertEqual(languages.lang_for_extension("java"), "java")
        self.assertEqual(languages.lang_for_extension(".groovy"), "groovy")
        self.assertEqual(languages.lang_for_extension(".scala"), "scala")

    def test_unknown_extension_returns_none(self):
        self.assertIsNone(languages.lang_for_extension(".rs"))

    def test_java_does_not_require_separate_compiler(self):
        """javac идёт с JDK — отдельный --compiler не нужен."""
        self.assertFalse(languages.LANGUAGES["java"]["requires_compiler"])

    def test_supported_list_is_human_readable(self):
        text = languages.supported_list()
        for lang in languages.ALL_LANGUAGES:
            self.assertIn(lang, text)

    def test_label_for_unknown_falls_back_to_key(self):
        self.assertEqual(languages.label_for("rust"), "rust")


if __name__ == "__main__":
    unittest.main()