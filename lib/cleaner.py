"""Очистка артефактов сборки."""

import os
import shutil


def clean(project_dir):
    """Удаляет build/ и отладочный keystore. Возвращает список удалённого."""
    removed = []
    build_dir = os.path.join(project_dir, "build")
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
        removed.append(build_dir)

    for name in (".debug.keystore",):
        path = os.path.join(project_dir, name)
        if os.path.exists(path):
            os.remove(path)
            removed.append(path)
    return removed