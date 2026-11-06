"""Тесты кэша сборки."""

import os
import time
import unittest

from helpers import TempDirTestCase

import cache


class FingerprintTest(TempDirTestCase):
    def test_same_content_same_fingerprint(self):
        path = os.path.join(self.tmpdir, "a.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")

        first = cache.fingerprint([path])
        second = cache.fingerprint([path])

        self.assertEqual(first, second)

    def test_changed_content_changes_fingerprint(self):
        path = os.path.join(self.tmpdir, "a.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        first = cache.fingerprint([path])

        time.sleep(0.01)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("xy")
        second = cache.fingerprint([path])

        self.assertNotEqual(first, second)

    def test_extra_strings_affect_fingerprint(self):
        path = os.path.join(self.tmpdir, "a.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")

        self.assertNotEqual(
            cache.fingerprint([path], extra=["cmd-a"]),
            cache.fingerprint([path], extra=["cmd-b"]),
        )

    def test_missing_files_are_ignored(self):
        self.assertEqual(cache.fingerprint(["/nope/a"]), "empty")

    def test_collect_inputs_is_recursive(self):
        nested = os.path.join(self.tmpdir, "res", "values")
        os.makedirs(nested)
        with open(os.path.join(nested, "strings.xml"), "w", encoding="utf-8") as handle:
            handle.write("<resources/>")

        found = cache.collect_inputs(self.tmpdir, ["*.xml"])

        self.assertEqual(len(found), 1)


class BuildCacheTest(TempDirTestCase):
    def _cache(self):
        return cache.BuildCache(os.path.join(self.tmpdir, "cache", "stages.json"))

    def test_fresh_after_remember(self):
        store = self._cache()
        store.remember("d8", "stamp-1")
        store.save()

        reloaded = self._cache()

        self.assertTrue(reloaded.is_fresh("d8", "stamp-1"))

    def test_stale_when_stamp_differs(self):
        store = self._cache()
        store.remember("d8", "stamp-1")

        self.assertFalse(store.is_fresh("d8", "stamp-2"))

    def test_stale_when_output_missing(self):
        """Кэш не должен врать, если результат стадии удалили руками."""
        output = os.path.join(self.tmpdir, "classes.dex")
        store = self._cache()
        store.remember("d8", "stamp-1", outputs=[output])
        store.save()

        self.assertFalse(store.is_fresh("d8", "stamp-1"))

        with open(output, "w", encoding="utf-8") as handle:
            handle.write("dex")
        self.assertTrue(store.is_fresh("d8", "stamp-1"))

    def test_broken_cache_file_is_ignored(self):
        path = os.path.join(self.tmpdir, "cache", "stages.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")

        store = cache.BuildCache(path)

        self.assertFalse(store.is_fresh("d8", "x"))

    def test_clear_forgets_everything(self):
        store = self._cache()
        store.remember("d8", "stamp-1")
        store.clear()

        self.assertFalse(store.is_fresh("d8", "stamp-1"))

    def test_unknown_stage_is_never_fresh(self):
        self.assertFalse(self._cache().is_fresh("nope", "x"))


if __name__ == "__main__":
    unittest.main()