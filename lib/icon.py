"""Иконка приложения: генерация простого PNG без внешних зависимостей.

Нужна, чтобы `builder-apk init` давал проект, который собирается сразу:
aapt2 ругается, если в манифесте есть @mipmap/ic_launcher, а ресурса нет.
"""

import struct
import zlib

DEFAULT_SIZE = 48
DEFAULT_COLOR = (0x2F, 0x6F, 0x9E)


def _chunk(kind, payload):
    """Собирает PNG-чанк: длина + тип + данные + CRC."""
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def make_icon(size=DEFAULT_SIZE, color=DEFAULT_COLOR):
    """Возвращает bytes готового PNG (RGBA, квадрат с закруглёнными углами)."""
    radius = max(2, size // 6)
    rows = []
    for y in range(size):
        row = bytearray([0])  # filter type 0 (None)
        for x in range(size):
            if _in_rounded_square(x, y, size, radius):
                row.extend((color[0], color[1], color[2], 255))
            else:
                row.extend((0, 0, 0, 0))
        rows.append(bytes(row))
    raw = b"".join(rows)

    header = struct.pack(
        ">IIBBBBB",
        size,
        size,
        8,  # bit depth
        6,  # color type RGBA
        0,  # compression
        0,  # filter
        0,  # interlace
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def _in_rounded_square(x, y, size, radius):
    """Попадает ли пиксель в квадрат со скруглёнными углами."""
    for corner_x in (radius - 1, size - radius):
        for corner_y in (radius - 1, size - radius):
            cx = corner_x + 0.5
            cy = corner_y + 0.5
            inside_x = (x < radius) if corner_x == radius - 1 else (x >= size - radius)
            inside_y = (y < radius) if corner_y == radius - 1 else (y >= size - radius)
            if inside_x and inside_y:
                dx = x + 0.5 - cx
                dy = y + 0.5 - cy
                if dx * dx + dy * dy > radius * radius:
                    return False
    return True


DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
}


def write_icons(res_dir, color=DEFAULT_COLOR):
    """Пишет ic_launcher.png во все плотности. Возвращает список путей."""
    import os

    paths = []
    for density, size in DENSITIES.items():
        target_dir = os.path.join(res_dir, "mipmap-%s" % density)
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, "ic_launcher.png")
        with open(path, "wb") as handle:
            handle.write(make_icon(size=size, color=color))
        paths.append(path)
    return paths