"""Кэш сборки: пропускать стадии, чьи входы не менялись.

Идея простая: для каждой стадии считаем отпечаток (mtime + размер + путь)
всех входных файлов плюс саму команду. Совпал с прошлым — стадию не запускаем.

Кэш битый или нечитаемый — не ошибка: просто собираем заново.
"""

import hashlib
import json
import os

CACHE_VERSION = 1


def file_fingerprint(path):
    """Отпечаток одного файла: путь, размер, mtime."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return "%s|%d|%d" % (path, stat.st_size, int(stat.st_mtime))


def fingerprint(paths, extra=()):
    """Хэш набора файлов + произвольных строк (например, команды)."""
    parts = []
    for path in sorted(paths):
        item = file_fingerprint(path)
        if item:
            parts.append(item)
    parts.extend(str(part) for part in extra)
    if not parts:
        return "empty"
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def collect_inputs(directory, patterns):
    """Собирает файлы под directory по glob-шаблонам (рекурсивно)."""
    import glob

    found = []
    for pattern in patterns:
        found.extend(glob.glob(os.path.join(directory, "**", pattern), recursive=True))
    return [path for path in found if os.path.isfile(path)]


class BuildCache(object):
    """Хранилище отпечатков стадий в build/.cache/stages.json."""

    def __init__(self, path):
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {"version": CACHE_VERSION, "stages": {}}
        if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
            return {"version": CACHE_VERSION, "stages": {}}
        data.setdefault("stages", {})
        return data

    def is_fresh(self, stage, stamp):
        """Совпадает ли отпечаток с сохранённым и цел ли результат."""
        saved = self.data["stages"].get(stage)
        if not saved or saved.get("stamp") != stamp:
            return False
        for output in saved.get("outputs", []):
            if not os.path.exists(output):
                return False
        return True

    def remember(self, stage, stamp, outputs=()):
        self.data["stages"][stage] = {
            "stamp": stamp,
            "outputs": [path for path in outputs if path],
        }

    def save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass  # кэш — оптимизация, не критичная часть сборки

    def clear(self):
        self.data = {"version": CACHE_VERSION, "stages": {}}
        self.save()