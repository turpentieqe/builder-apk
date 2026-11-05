"""Тесты генерации иконки (PNG собирается вручную, без Pillow)."""

import os
import struct
import unittest

from helpers import TempDirTestCase

import icon


def png_size(data):
    """Читает ширину/высоту из IHDR."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("это не PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class MakeIconTest(unittest.TestCase):
    def test_returns_valid_png_with_requested_size(self):
        data = icon.make_icon(size=48)

        self.assertEqual(png_size(data), (48, 48))

    def test_bigger_density_has_bigger_png(self):
        small = icon.make_icon(size=48)
        large = icon.make_icon(size=144)

        self.assertLess(len(small), len(large))
        self.assertEqual(png_size(large), (144, 144))

    def test_png_ends_with_iend(self):
        data = icon.make_icon(size=48)

        self.assertIn(b"IEND", data[-12:])


class WriteIconsTest(TempDirTestCase):
    def test_writes_all_densities(self):
        paths = icon.write_icons(self.tmpdir)

        names = {os.path.basename(os.path.dirname(p)) for p in paths}
        self.assertEqual(names, {"mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi"})
        for path in paths:
            self.assertTrue(os.path.exists(path))
            with open(path, "rb") as handle:
                png_size(handle.read())


if __name__ == "__main__":
    unittest.main()