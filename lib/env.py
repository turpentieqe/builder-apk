"""Обнаружение установленных Android SDK (Termux-специфика).

Зачем: в Termux люди ставят SDK двумя путями — через `pkg install android-sdk`
(бинарники появляются в $PREFIX/bin) и распаковкой официальных cmdline-tools
в домашний каталог. Второй путь даёт **x86-64** бинарники, которые на телефоне
не запускаются вовсе. Молчаливое «aapt2: команда не найдена» — плохой UX,
поэтому показываем именно эту причину.
"""

import glob
import os
import platform
import struct

ARCH_MAP = {
    "x86_64": "x86-64",
    "amd64": "x86-64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}

ARCH_KEYS = ["aarch64", "x86-64", "arm"]


def host_arch():
    """Архитектура текущей машины в нотации ELF."""
    machine = platform.machine().lower()
    return ARCH_MAP.get(machine, machine)


def elf_arch(path):
    """Читает e_machine из ELF-заголовка. None — не ELF или не читается."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(20)
    except OSError:
        return None
    if len(header) < 20 or header[:4] != b"\x7fELF":
        return None
    endian = "<" if header[5] == 1 else ">"
    machine = struct.unpack_from(endian + "H", header, 18)[0]
    if machine == 183:
        return "aarch64"
    if machine == 62:
        return "x86-64"
    if machine == 40:
        return "arm"
    return "machine-%d" % machine


def is_runnable(path):
    """Проверяет, что бинарник подходит текущей архитектуре."""
    arch = elf_arch(path)
    if arch is None:
        return True  # не ELF (скрипт) — пусть решает запуск
    return arch == host_arch()


def arch_mismatch_hint(path):
    """Текст ошибки про чужую архитектуру."""
    return "бинарник %s: собран под %s, а устройство %s — запускать бесполезно" % (
        path,
        elf_arch(path),
        host_arch(),
    )


def discover_build_tools(extra_roots=()):
    """Ищет каталоги build-tools/* с d8.jar и возвращает список кандидатов."""
    roots = [
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        os.path.expanduser("~/android-sdk"),
        os.path.expanduser("~/Android/Sdk"),
        os.path.expanduser("~/tools/android-sdk"),
        os.path.expanduser("~/projects/tools/android-sdk"),
    ]
    roots.extend(extra_roots)

    found = []
    for root in roots:
        if not root:
            continue
        pattern = os.path.join(root, "build-tools", "*")
        for candidate in sorted(glob.glob(pattern)):
            if os.path.exists(os.path.join(candidate, "lib", "d8.jar")):
                found.append(candidate)
    return found


def discover_kotlinc(extra_roots=()):
    """Ищет kotlinc в типичных местах Termux/домашнего каталога."""
    import shutil

    system = shutil.which("kotlinc")
    if system:
        return system

    roots = [
        os.path.expanduser("~/tools/kotlin"),
        os.path.expanduser("~/kotlin"),
        os.path.expanduser("~/projects/tools/kotlin"),
        os.path.expanduser("~/.sdkman/candidates/kotlin/current"),
    ]
    roots.extend(extra_roots)
    for root in roots:
        candidate = os.path.join(root, "kotlinc", "bin", "kotlinc")
        if os.path.exists(candidate):
            return candidate
    return None


def discover_android_jar(build_tools, target_sdk=None):
    """Ищет android.jar рядом с build-tools."""
    if not build_tools:
        return None
    sdk_root = os.path.dirname(os.path.dirname(build_tools))
    platforms = os.path.join(sdk_root, "platforms")
    if target_sdk is not None:
        candidate = os.path.join(platforms, "android-%d" % target_sdk, "android.jar")
        if os.path.exists(candidate):
            return candidate
    jars = sorted(glob.glob(os.path.join(platforms, "android-*", "android.jar")))
    return jars[-1] if jars else None