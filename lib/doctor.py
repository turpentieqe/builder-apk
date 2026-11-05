"""Проверка цепочки инструментов Android-сборки.

Модуль отвечает за диагностику окружения: находит каждый бинарник цепочки
(aapt2, kotlinc, d8, zipalign, apksigner, java), определяет версию и статус.
"""

import os
import re
import shutil
import subprocess

import env

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_MISSING = "missing"
STATUS_BROKEN = "broken"
STATUS_ABSENT = "absent"  # необязательный инструмент, которого нет вовсе

# Провал цепочки — только эти статусы у обязательных инструментов.
_FAILING_STATUSES = (STATUS_MISSING, STATUS_BROKEN, STATUS_ABSENT)

_VERSION_PATTERNS = {
    "aapt2": re.compile(r"(\d+\.\d+(?:\.\d+)?)"),
    "apksigner": re.compile(r"(\d+\.\d+(?:\.\d+)?)"),
    "java": re.compile(r'version "([^"]+)"'),
    "kotlinc": re.compile(r"(\d+\.\d+\.\d+)"),
    "zipalign": re.compile(r"(\d+\.\d+(?:\.\d+)?)"),
}


def _run(cmd, timeout=30):
    """Запускает команду, возвращает (код, stdout, stderr) либо None."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace").strip(),
        proc.stderr.decode("utf-8", "replace").strip(),
    )


def parse_version(tool, text):
    """Вытаскивает версию из вывода инструмента."""
    pattern = _VERSION_PATTERNS.get(tool)
    if not pattern or not text:
        return None
    match = pattern.search(text)
    return match.group(1) if match else None


def _probe_binary(tool, path, version_args, hint, if_absent=None):
    """Проверяет один бинарник: наличие + архитектура + запуск + версия.

    if_absent — статус, если бинарника нет вовсе (по умолчанию missing).
    """
    if not path or not os.path.exists(path) or not os.access(path, os.X_OK):
        if not path:
            detail = hint
            status = if_absent or STATUS_MISSING
        else:
            detail = "%s: файл не найден или не исполняемый" % hint
            status = STATUS_BROKEN
        return {"status": status, "path": path, "version": None, "hint": detail}

    # Архитектура: частая ловушка в Termux — x86-64 SDK на ARM-телефоне.
    if not env.is_runnable(path):
        return {
            "status": STATUS_BROKEN,
            "path": path,
            "version": None,
            "hint": hint + " | " + env.arch_mismatch_hint(path),
        }

    result = _run([path] + version_args)
    if result is None:
        return {
            "status": STATUS_BROKEN,
            "path": path,
            "version": None,
            "hint": "%s: не запускается" % hint,
        }

    code, stdout, stderr = result
    combined = "\n".join(part for part in (stdout, stderr) if part)

    # Ненулевой код на запросе версии = сломанный инструмент
    # (например, нативная библиотека не грузится, как jansi в Termux).
    if code != 0:
        return {
            "status": STATUS_BROKEN,
            "path": path,
            "version": None,
            "hint": "%s: падает с кодом %d" % (hint, code),
        }

    return {
        "status": STATUS_OK,
        "path": path,
        "version": parse_version(tool, combined),
        "hint": None,
    }


def _find_binary(name, build_tools, extra_dirs=(), use_path=True):
    """Ищет бинарник: сначала в build-tools, потом в extra_dirs, потом в PATH."""
    if not name:
        return None
    if build_tools:
        candidate = os.path.join(build_tools, name)
        if os.path.exists(candidate):
            return candidate
    for directory in extra_dirs:
        if not directory:
            continue
        candidate = os.path.join(directory, name)
        if os.path.exists(candidate):
            return candidate
    return shutil.which(name) if use_path else None


def check_chain(build_tools=None, android_jar=None, java_bin="java", kotlinc=None, use_path=True):
    """Проверяет всю цепочку и возвращает словарь {tool: status-dict}.

    use_path=False — не смотреть в PATH (нужно тестам и режиму строгой проверки SDK).
    """
    build_tools = build_tools or ""
    extra_dirs = (build_tools,)

    report = {
        "java": _probe_binary(
            "java",
            _find_binary(java_bin, None, extra_dirs, use_path),
            ["-version"],
            "установите openjdk (pkg install openjdk-21)",
        ),
        "aapt2": _probe_binary(
            "aapt2",
            _find_binary("aapt2", build_tools, extra_dirs, use_path),
            ["version"],
            "нужен aapt2 из Android SDK build-tools",
        ),
        "zipalign": _probe_binary(
            "zipalign",
            _find_binary("zipalign", build_tools, extra_dirs, use_path),
            ["--version"],
            "zipalign необязателен: v2-подпись работает и без выравнивания",
            if_absent=STATUS_ABSENT,
        ),
        "apksigner": _probe_binary(
            "apksigner",
            _find_binary("apksigner", build_tools, extra_dirs, use_path),
            ["--version"],
            "нужен apksigner из Android SDK build-tools",
        ),
    }

    report["d8"] = _check_d8(build_tools)
    report["kotlinc"] = _probe_binary(
        "kotlinc",
        kotlinc or _find_binary("kotlinc", None, extra_dirs, use_path),
        ["-version"],
        "kotlinc нужен только для Kotlin-проектов",
    )
    report["android_jar"] = _check_android_jar(android_jar, build_tools)
    return report


def _check_d8(build_tools):
    """d8 живёт как jar в build-tools/<ver>/lib/d8.jar."""
    hint = "d8.jar нужен для конвертации классов в dex"
    if not build_tools:
        return {"status": STATUS_MISSING, "path": None, "version": None, "hint": hint}

    jar = os.path.join(build_tools, "lib", "d8.jar")
    if not os.path.exists(jar):
        return {"status": STATUS_MISSING, "path": None, "version": None, "hint": hint}

    return {"status": STATUS_OK, "path": jar, "version": None, "hint": None}


def _check_android_jar(android_jar, build_tools):
    """android.jar из platforms/android-XX обязателен для aapt2 link и d8."""
    hint = "android.jar обязателен: укажите --android-jar или --sdk"
    candidates = []
    if android_jar:
        candidates.append(android_jar)
    if build_tools:
        # build-tools/34.0.0 -> ../../platforms/android-XX/android.jar
        sdk_root = os.path.dirname(os.path.dirname(build_tools))
        platforms = os.path.join(sdk_root, "platforms")
        if os.path.isdir(platforms):
            for entry in sorted(os.listdir(platforms)):
                candidates.append(os.path.join(platforms, entry, "android.jar"))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return {"status": STATUS_OK, "path": candidate, "version": None, "hint": None}

    return {"status": STATUS_MISSING, "path": None, "version": None, "hint": hint}


def has_failures(report, extra_required=()):
    """Провал — только missing/broken у обязательных инструментов.

    По умолчанию обязательны: java, aapt2, d8, apksigner, android_jar.
    kotlinc и zipalign необязательны — их отсутствие лишь предупреждение
    (статус absent/warning). extra_required поднимает любой инструмент
    (например kotlinc для Kotlin-проекта) до обязательного.
    """
    optional = ("kotlinc", "zipalign")
    for tool, info in report.items():
        if info.get("status") not in _FAILING_STATUSES:
            continue
        if tool in optional and tool not in extra_required:
            continue
        return True
    return False


def format_report(report):
    """Табличка для терминала."""
    order = ["java", "aapt2", "d8", "kotlinc", "zipalign", "apksigner", "android_jar"]
    marks = {
        STATUS_OK: "OK  ",
        STATUS_WARNING: "WARN",
        STATUS_MISSING: "MISS",
        STATUS_BROKEN: "BAD ",
        STATUS_ABSENT: "WARN",
    }
    lines = ["Инструмент       Статус  Версия         Путь"]
    for tool in order:
        info = report.get(tool)
        if not info:
            continue
        lines.append(
            "%-16s %-7s %-14s %s"
            % (
                tool,
                marks.get(info["status"], "??? "),
                info.get("version") or "-",
                info.get("path") or "-",
            )
        )
    hints = [
        "  %s: %s" % (tool, report[tool]["hint"])
        for tool in order
        if tool in report and report[tool].get("hint")
    ]
    if hints:
        lines.append("")
        lines.append("Подсказки:")
        lines.extend(hints)
    return "\n".join(lines)