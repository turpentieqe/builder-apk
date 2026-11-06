#!/usr/bin/env python3
"""Инспекция APK: badging, подпись, разрешения.

Модуль ничего не собирает — только читает готовый APK через aapt/apksigner.
Парсинг вывода вынесен в отдельные функции, чтобы тестировать без SDK.
"""

import os
import re
import shutil
import subprocess


def _run(cmd, timeout=60):
    """Запускает команду и возвращает (код, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as error:
        return 127, "", str(error)
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def parse_badging(text):
    """Разбирает вывод `aapt dump badging` в словарь."""
    data = {
        "package": None,
        "version_code": None,
        "version_name": None,
        "label": None,
        "sdk_version": None,
        "target_sdk": None,
        "permissions": [],
        "launchable": None,
        "native_code": [],
    }
    if not text:
        return data

    package_re = re.compile(
        r"package: name='([^']*)' versionCode='([^']*)' versionName='([^']*)'"
    )
    label_re = re.compile(r"application-label(?:-[a-z]{2})?:'([^']*)'")
    sdk_re = re.compile(r"(?:min)?sdkVersion:'([^']*)'", re.IGNORECASE)
    target_re = re.compile(r"targetSdkVersion:'([^']*)'")
    perm_re = re.compile(r"uses-permission: name='([^']*)'")
    launch_re = re.compile(r"launchable-activity: name='([^']*)'")
    native_re = re.compile(r"native-code: '([^']*)'")

    for line in text.splitlines():
        line = line.strip()
        match = package_re.match(line)
        if match:
            data["package"] = match.group(1)
            data["version_code"] = match.group(2)
            data["version_name"] = match.group(3)
            continue
        match = label_re.match(line)
        if match and data["label"] is None:
            data["label"] = match.group(1)
            continue
        match = sdk_re.match(line)
        if match:
            data["sdk_version"] = match.group(1)
            continue
        match = target_re.match(line)
        if match:
            data["target_sdk"] = match.group(1)
            continue
        match = perm_re.match(line)
        if match:
            data["permissions"].append(match.group(1))
            continue
        match = launch_re.match(line)
        if match:
            data["launchable"] = match.group(1)
            continue
        match = native_re.match(line)
        if match:
            data["native_code"].extend(match.group(1).split())
            continue
    return data


def parse_certs(text):
    """Разбирает `apksigner verify --print-certs` в структуру."""
    info = {"signed": False, "schemes": [], "signers": [], "dn": None, "sha256": None}
    if not text:
        return info

    scheme_re = re.compile(r"Verified using (v[0-9.]+) scheme")
    dn_re = re.compile(r"certificate DN: (.+)$")
    sha_re = re.compile(r"certificate SHA-256 digest: ([0-9a-f]+)")
    # В некоторых версиях apksigner формат другой: «V3.0 Signer: certificate DN: …»
    alt_dn_re = re.compile(r"^V[0-9.]+ Signer: certificate DN: (.+)$")

    for line in text.splitlines():
        line = line.strip()
        match = scheme_re.search(line)
        if match:
            info["schemes"].append(match.group(1))
            info["signed"] = True
            continue
        match = alt_dn_re.match(line)
        if match:
            info["dn"] = match.group(1).strip()
            info["signed"] = True
            continue
        match = dn_re.search(line)
        if match:
            info["dn"] = match.group(1).strip()
            info["signed"] = True
            continue
        match = sha_re.search(line)
        if match:
            info["sha256"] = match.group(1)
            info["signed"] = True
            continue
    return info


def human_size(num_bytes):
    """Человекочитаемый размер."""
    step = 1024.0
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < step or unit == "GiB":
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.1f %s" % (value, unit)
        value /= step
    return "%.1f GiB" % value


def detect_badging_tool(explicit=None):
    """Выбирает aapt2, если он есть: он стабильнее и есть во всех новых SDK.

    Порядок: явно заданный → aapt2 → aapt.
    """
    if explicit:
        return explicit
    for candidate in ("aapt2", "aapt"):
        path = shutil.which(candidate)
        if path:
            return path
    return "aapt"


def inspect(apk_path, aapt=None, apksigner="apksigner"):
    """Читает APK через aapt2/aapt и apksigner, возвращает словарь."""
    result = {
        "path": os.path.abspath(apk_path),
        "exists": os.path.exists(apk_path),
        "size_bytes": None,
        "badging": {},
        "certs": {},
        "tool": None,
        "errors": [],
    }
    if not result["exists"]:
        result["errors"].append("файл не найден: %s" % apk_path)
        return result

    result["size_bytes"] = os.path.getsize(apk_path)

    tool = detect_badging_tool(aapt)
    result["tool"] = os.path.basename(tool)
    code, stdout, stderr = _run([tool, "dump", "badging", apk_path], timeout=120)
    if code != 0:
        result["errors"].append(
            "%s dump badging: %s" % (result["tool"], stderr.strip() or "код %d" % code)
        )
    badging = parse_badging(stdout)

    # aapt (v1) не умеет часть полей — добираем aapt2, если он доступен.
    if not badging.get("package") and result["tool"] != "aapt2":
        aapt2 = shutil.which("aapt2")
        if aapt2:
            code2, stdout2, _stderr2 = _run([aapt2, "dump", "badging", apk_path], timeout=120)
            if code2 == 0 and parse_badging(stdout2).get("package"):
                badging = parse_badging(stdout2)
                result["tool"] = "aapt2"
    result["badging"] = badging

    code, stdout, stderr = _run([apksigner, "verify", "--print-certs", apk_path])
    # apksigner возвращает 0 для валидной подписи, 1 — для неподписанного/битого.
    if code != 0 and "DOES NOT VERIFY" not in (stdout + stderr).upper():
        result["errors"].append(
            "apksigner verify: %s" % (stderr.strip() or "код %d" % code)
        )
    result["certs"] = parse_certs(stdout)
    return result


def format_report(data):
    """Текстовый отчёт для терминала."""
    lines = ["APK: %s" % data["path"]]
    if data.get("tool"):
        lines.append("Разбор: %s" % data["tool"])
    if data.get("size_bytes") is not None:
        lines.append("Размер: %s" % human_size(data["size_bytes"]))

    badging = data.get("badging") or {}
    if badging.get("package"):
        lines.append("")
        lines.append("Пакет:      %s" % badging.get("package"))
        lines.append(
            "Версия:     %s (code %s)"
            % (badging.get("version_name"), badging.get("version_code"))
        )
        if badging.get("label"):
            lines.append("Название:   %s" % badging["label"])
        lines.append(
            "SDK:        min %s / target %s"
            % (badging.get("sdk_version"), badging.get("target_sdk"))
        )
        if badging.get("launchable"):
            lines.append("Activity:   %s" % badging["launchable"])
        if badging.get("native_code"):
            lines.append("Native:     %s" % ", ".join(badging["native_code"]))

        permissions = badging.get("permissions") or []
        lines.append("")
        if permissions:
            lines.append("Разрешения (%d):" % len(permissions))
            for perm in permissions:
                lines.append("  - %s" % perm)
        else:
            lines.append("Разрешений нет.")

    certs = data.get("certs") or {}
    lines.append("")
    if certs.get("signed"):
        schemes = ", ".join(certs.get("schemes") or []) or "схема неизвестна"
        lines.append("Подпись:    есть (%s)" % schemes)
        if certs.get("dn"):
            lines.append("Certificate: %s" % certs["dn"])
        if certs.get("sha256"):
            lines.append("SHA-256:    %s" % certs["sha256"])
    else:
        lines.append("Подпись:    НЕТ — такой APK не установится на устройство.")

    if data.get("errors"):
        lines.append("")
        lines.append("Ошибки:")
        for error in data["errors"]:
            lines.append("  ! %s" % error)
    return "\n".join(lines)