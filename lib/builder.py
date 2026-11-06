"""Сборка APK по шагам без Gradle: aapt2 -> (kotlinc|javac) -> d8 -> zip -> zipalign -> apksigner.

Главный принцип: никакая стадия не «проваливается молча». Каждый шаг проверяет
код возврата, а подозрительные предупреждения из stderr попадают в warnings,
а не растворяются в выводе (как было с jansi в Termux).
"""

import glob
import os
import shutil
import subprocess
import time

import cache
import env
import languages

STAGES = ("aapt2-compile", "aapt2-link", "compile", "d8", "package", "zipalign", "sign")

# Предупреждения, которые встречаются в реальных сборках на Termux.
# Порядок важен: первое совпадение выигрывает, поэтому jansi идёт раньше
# общего UnsatisfiedLinkError (jansi-ошибка содержит оба маркера).
KNOWN_STDERR_PATTERNS = (
    ("jansi", "kotlin-компилятор не смог загрузить jansi (нативный модуль) — на результат не влияет"),
    ("warning: [options] bootstrap class path", "javac предупреждает про bootclasspath"),
    ("UnsatisfiedLinkError", "нативная библиотека не загрузилась — проверьте java/NDK"),
)


class BuildError(RuntimeError):
    """Стадия сборки завершилась ошибкой."""

    def __init__(self, stage, message, output=""):
        super().__init__("[%s] %s" % (stage, message))
        self.stage = stage
        self.output = output


def _run(cmd, stage, cwd=None, timeout=1800):
    """Выполняет команду стадии и бросает BuildError при ненулевом коде."""
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise BuildError(stage, "команда не найдена: %s" % cmd[0])
    except (OSError, subprocess.SubprocessError) as error:
        raise BuildError(stage, "не удалось запустить: %s" % error)

    duration = time.time() - started
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise BuildError(
            stage,
            "код %d" % proc.returncode,
            output=(stdout + "\n" + stderr).strip(),
        )
    return {"stage": stage, "duration": duration, "stdout": stdout, "stderr": stderr}


def scan_stderr(stage, stderr_text):
    """Ищет в stderr известные «шумные» предупреждения и возвращает список."""
    warnings = []
    if not stderr_text:
        return warnings
    lowered = stderr_text.lower()
    for needle, message in KNOWN_STDERR_PATTERNS:
        if needle.lower() not in lowered:
            continue
        warnings.append({"stage": stage, "message": message})
        # Один диагностический корень — одно предупреждение: если поймали jansi,
        # не сыпем следом общий UnsatisfiedLinkError про ту же библиотеку.
        if needle == "jansi":
            break
    return warnings


def find_sources(src_dir, lang):
    """Возвращает список файлов исходников нужного языка."""
    pattern = "*" + languages.extension_for(lang)
    return sorted(glob.glob(os.path.join(src_dir, "**", pattern), recursive=True))


def detect_lang(project_dir, prefer=None):
    """Определяет язык по содержимому src/.

    prefer — явно указанный пользователем язык (--lang): побеждает автоопределение.
    Порядок автоопределения задан в languages.LANGUAGES.
    """
    src_root = os.path.join(project_dir, "src")

    if prefer:
        prefer = prefer.lower()
        if prefer not in languages.ALL_LANGUAGES:
            raise BuildError(
                "resolve",
                "неизвестный язык %r, поддерживаются: %s"
                % (prefer, languages.supported_list()),
            )
        sources = find_sources(src_root, prefer)
        if not sources:
            raise BuildError(
                "resolve",
                "не найдено исходников *%s в %s (--lang %s)"
                % (languages.extension_for(prefer), src_root, prefer),
            )
        return prefer, sources

    for lang in languages.ALL_LANGUAGES:
        sources = find_sources(src_root, lang)
        if sources:
            return lang, sources
    return None, []


def stat_size(path):
    """Размер файла или None."""
    return os.path.getsize(path) if path and os.path.exists(path) else None


def _find_tool(build_tools, name):
    """Ищет инструмент: build-tools (если архитектура подходит), затем PATH.

    Именно архитектурная проверка спасает Termux: в распакованном SDK лежат
    x86-64 бинарники, а они на телефоне дают «Exec format error».
    """
    candidate = os.path.join(build_tools, name) if build_tools else None
    if candidate and os.path.exists(candidate) and env.is_runnable(candidate):
        return candidate
    found = shutil.which(name)
    if found:
        return found
    return candidate  # пусть стадия упадёт с понятной ошибкой


def resolve_sdk(sdk=None, build_tools=None):
    """Определяет каталог build-tools и android.jar из --sdk/--build-tools или ANDROID_HOME."""
    sdk_root = sdk or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")

    if build_tools:
        bt = build_tools
    elif sdk_root and os.path.isdir(os.path.join(sdk_root, "build-tools")):
        candidates = sorted(os.listdir(os.path.join(sdk_root, "build-tools")))
        if not candidates:
            raise BuildError("resolve", "в %s/build-tools пусто" % sdk_root)
        bt = os.path.join(sdk_root, "build-tools", candidates[-1])
    else:
        bt = None

    if not bt:
        raise BuildError(
            "resolve",
            "не найден Android SDK: задайте ANDROID_HOME или --sdk/--build-tools",
        )
    return bt


def resolve_android_jar(android_jar=None, build_tools=None, target_sdk=34):
    """Ищет android.jar нужной платформы."""
    if android_jar:
        if not os.path.exists(android_jar):
            raise BuildError("resolve", "android.jar не найден: %s" % android_jar)
        return android_jar

    if build_tools:
        sdk_root = os.path.dirname(os.path.dirname(build_tools))
        platforms = os.path.join(sdk_root, "platforms")
        for name in ("android-%d" % target_sdk,):
            candidate = os.path.join(platforms, name, "android.jar")
            if os.path.exists(candidate):
                return candidate
        if os.path.isdir(platforms):
            found = sorted(
                glob.glob(os.path.join(platforms, "android-*", "android.jar"))
            )
            if found:
                return found[-1]

    raise BuildError(
        "resolve",
        "android.jar не найден (ищите в $ANDROID_HOME/platforms/android-%d/)" % target_sdk,
    )


def _compile_groovy(groovyc, android_jar, classes_dir, sources):
    """groovyc: компиляция Groovy (JVM-байткод, d8 дальше тот же)."""
    return [
        groovyc,
        "--classpath",
        android_jar,
        "-d",
        classes_dir,
    ] + sources


def _compile_scala(scalac, android_jar, classes_dir, sources):
    """scalac: компиляция Scala."""
    return [
        scalac,
        "-classpath",
        android_jar,
        "-d",
        classes_dir,
    ] + sources


def compile_command(lang, android_jar, classes_dir, sources, compiler=None, java_release=None):
    """Собирает команду компиляции для любого поддерживаемого языка.

    Единая точка входа: раньше ветвление было зашито в двух местах, теперь
    добавление языка не требует трогать остальную сборку.
    """
    if lang not in languages.ALL_LANGUAGES:
        raise BuildError(
            "compile", "неизвестный язык %r (поддерживаются: %s)" % (lang, languages.supported_list())
        )

    if lang == "java":
        return _compile_java(android_jar, classes_dir, sources, java_release=java_release)

    info = languages.LANGUAGES[lang]
    binary = compiler or shutil.which(info["compiler"])
    if not binary:
        raise BuildError(
            "compile",
            "%s не найден — укажите явный путь или используйте --lang java "
            "(например: --compiler /path/to/%s)" % (info["compiler"], info["compiler"]),
        )

    if lang == "kotlin":
        return _compile_kotlin(binary, android_jar, classes_dir, sources)
    if lang == "groovy":
        return _compile_groovy(binary, android_jar, classes_dir, sources)
    return _compile_scala(binary, android_jar, classes_dir, sources)


def _compile_kotlin(kotlinc, android_jar, classes_dir, sources):
    """kotlinc: компиляция Kotlin в JVM-классы."""
    return [
        kotlinc,
        "-language-version",
        "1.9",
        "-classpath",
        android_jar,
        "-d",
        classes_dir,
    ] + sources


def _compile_java(android_jar, classes_dir, sources, java_release=None):
    """javac: компиляция Java под Android bootclasspath.

    java_release — целевая версия Java (по умолчанию 8). Android требует
    `-bootclasspath` (а не `--release`) при source/target <= 8, и наоборот:
    при target >= 9 javac запрещает `-bootclasspath`, поэтому переключаемся
    на `--release` без bootclasspath.
    """
    version = str(java_release or 8)
    cmd = ["javac", "-source", version, "-target", version, "-d", classes_dir]
    if int(version) <= 8:
        cmd[1:1] = ["-bootclasspath", android_jar]
    else:
        cmd[1:1] = ["-classpath", android_jar]
    return cmd + sources


def _d8_cmd(java, d8_jar, android_jar, min_sdk, dex_dir, class_files, extra_jars=()):
    """d8: JVM-классы -> classes.dex."""
    return [
        java,
        "-cp",
        d8_jar,
        "com.android.tools.r8.D8",
        "--release",
        "--lib",
        android_jar,
        "--min-api",
        str(min_sdk),
        "--output",
        dex_dir,
    ] + list(class_files) + list(extra_jars)


def build(
    project_dir,
    sdk=None,
    build_tools=None,
    android_jar=None,
    kotlinc=None,
    release=False,
    output=None,
    json_output=False,
    min_sdk=21,
    target_sdk=34,
    keystore=None,
    keystore_pass=None,
    key_alias=None,
    lang=None,
    compiler=None,
    use_cache=True,
    version_code=1,
    version_name="1.0",
    java_release=None,
):
    """Собирает APK. Возвращает код выхода (0 — успех)."""
    import json as _json

    report = {"project": os.path.abspath(project_dir), "stages": [], "warnings": [], "apk": None}
    try:
        stages, warnings, apk = _build_inner(
            project_dir=project_dir,
            sdk=sdk,
            build_tools=build_tools,
            android_jar=android_jar,
            kotlinc=kotlinc,
            release=release,
            output=output,
            min_sdk=min_sdk,
            target_sdk=target_sdk,
            keystore=keystore,
            keystore_pass=keystore_pass,
            key_alias=key_alias,
            lang=lang,
            compiler=compiler,
            use_cache=use_cache,
            version_code=version_code,
            version_name=version_name,
            java_release=java_release,
        )
        report["stages"] = stages
        report["warnings"] = warnings
        report["apk"] = apk
    except BuildError as error:
        report["error"] = {"stage": error.stage, "message": str(error)}
        if json_output:
            print(_json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_failure(report, error)
        return 1

    if json_output:
        print(_json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_success(report)
    return 0


def _build_inner(
    project_dir,
    sdk,
    build_tools,
    android_jar,
    kotlinc,
    release,
    output,
    min_sdk,
    target_sdk,
    keystore,
    keystore_pass,
    key_alias,
    lang=None,
    compiler=None,
    use_cache=True,
    version_code=1,
    version_name="1.0",
    java_release=None,
):
    stages = []
    warnings = []

    project_dir = os.path.abspath(project_dir)
    manifest = os.path.join(project_dir, "AndroidManifest.xml")
    res_dir = os.path.join(project_dir, "res")

    # В старой раскладке (как у dragon-nest) манифест и ресурсы лежат в app/.
    if not os.path.exists(manifest):
        alt = os.path.join(project_dir, "app", "src", "AndroidManifest.xml")
        if os.path.exists(alt):
            manifest = alt
            res_dir = os.path.join(project_dir, "app", "res")
    if not os.path.exists(manifest):
        raise BuildError("resolve", "AndroidManifest.xml не найден в %s" % project_dir)

    lang, sources = detect_lang(project_dir, prefer=lang)
    if not lang:
        lang, sources = detect_lang(os.path.join(project_dir, "app"), prefer=lang)
    if not lang:
        raise BuildError(
            "resolve",
            "не найдено исходников (%s) в src/" % languages.supported_list(),
        )

    bt = resolve_sdk(sdk=sdk, build_tools=build_tools)
    jar = resolve_android_jar(android_jar=android_jar, build_tools=bt, target_sdk=target_sdk)
    d8_jar = os.path.join(bt, "lib", "d8.jar")
    if not os.path.exists(d8_jar):
        raise BuildError("resolve", "d8.jar не найден: %s" % d8_jar)

    work = os.path.join(project_dir, "build")
    tmp = os.path.join(work, ".tmp")
    # При включённом кэше промежуточные результаты надо сохранять между сборками,
    # иначе пропущенная стадия оставит нас без своих выходов.
    if os.path.isdir(tmp) and not use_cache:
        shutil.rmtree(tmp)
    classes_dir = os.path.join(tmp, "classes")
    dex_dir = os.path.join(tmp, "dex")
    os.makedirs(classes_dir, exist_ok=True)
    os.makedirs(dex_dir, exist_ok=True)

    aapt2 = _find_tool(bt, "aapt2")
    zipalign = _find_tool(bt, "zipalign")
    apksigner = _find_tool(bt, "apksigner")

    # 1. aapt2 compile
    res_zip = os.path.join(tmp, "res.zip")
    result = _run([aapt2, "compile", "--dir", res_dir, "-o", res_zip], "aapt2-compile")
    stages.append(_stage_entry(result, stat_size(res_zip)))
    warnings.extend(scan_stderr("aapt2-compile", result["stderr"]))

    # 2. aapt2 link
    unsigned = os.path.join(tmp, "app.unsigned.apk")
    result = _run(
        [
            aapt2,
            "link",
            "-o",
            unsigned,
            "-I",
            jar,
            "--manifest",
            manifest,
            res_zip,
            "--min-sdk-version",
            str(min_sdk),
            "--target-sdk-version",
            str(target_sdk),
            "--version-code",
            str(version_code),
            "--version-name",
            str(version_name),
            "--auto-add-overlay",
        ],
        "aapt2-link",
    )
    stages.append(_stage_entry(result, stat_size(unsigned)))
    warnings.extend(scan_stderr("aapt2-link", result["stderr"]))
    return _compile_and_pack(
        stages,
        warnings,
        lang=lang,
        sources=sources,
        kotlinc=kotlinc,
        jar=jar,
        d8_jar=d8_jar,
        min_sdk=min_sdk,
        classes_dir=classes_dir,
        dex_dir=dex_dir,
        unsigned=unsigned,
        project_dir=project_dir,
        release=release,
        output=output,
        bt=bt,
        zipalign=zipalign,
        apksigner=apksigner,
        keystore=keystore,
        keystore_pass=keystore_pass,
        key_alias=key_alias,
        compiler=compiler,
        use_cache=use_cache,
        res_dir=res_dir,
        manifest=manifest,
        java_release=java_release,
    )


def _compile_and_pack(
    stages,
    warnings,
    lang,
    sources,
    kotlinc,
    jar,
    d8_jar,
    min_sdk,
    classes_dir,
    dex_dir,
    unsigned,
    project_dir,
    release,
    output,
    bt,
    zipalign,
    apksigner,
    keystore,
    keystore_pass,
    key_alias,
    compiler=None,
    use_cache=True,
    res_dir=None,
    manifest=None,
    java_release=None,
):
    """Стадии 3-7: компиляция, dex, упаковка, выравнивание, подпись."""
    store = cache.BuildCache(os.path.join(project_dir, "build", ".cache", "stages.json"))

    # 3. Компиляция — единая точка входа для всех языков
    cmd = compile_command(
        lang, jar, classes_dir, sources, compiler=compiler or kotlinc, java_release=java_release
    )
    compile_stamp = cache.fingerprint(sources, extra=cmd)
    if use_cache and store.is_fresh("compile", compile_stamp):
        stages.append(_skipped("compile"))
    else:
        result = _run(cmd, "compile")
        stages.append(_stage_entry(result, None))
        warnings.extend(scan_stderr("compile", result["stderr"]))
        store.remember("compile", compile_stamp, outputs=[classes_dir])

    # 4. d8
    class_files = sorted(glob.glob(os.path.join(classes_dir, "**", "*.class"), recursive=True))
    if not class_files:
        raise BuildError("d8", "после компиляции нет ни одного .class")
    java_bin = shutil.which("java") or "java"
    extra_jars = []
    if lang in ("kotlin",):
        stdlib = _find_kotlin_stdlib(compiler or kotlinc or shutil.which("kotlinc"))
        if stdlib:
            extra_jars.append(stdlib)
        else:
            warnings.append(
                {"stage": "d8", "message": "kotlin-stdlib.jar не найден — APK упадёт на старте"}
            )
    dex_file = os.path.join(dex_dir, "classes.dex")
    d8_cmd = _d8_cmd(java_bin, d8_jar, jar, min_sdk, dex_dir, class_files, extra_jars)
    d8_stamp = cache.fingerprint(class_files, extra=d8_cmd)
    if use_cache and store.is_fresh("d8", d8_stamp):
        stages.append(_skipped("d8"))
    else:
        result = _run(d8_cmd, "d8")
        stages.append(_stage_entry(result, stat_size(dex_file)))
        warnings.extend(scan_stderr("d8", result["stderr"]))
        store.remember("d8", d8_stamp, outputs=[dex_file])

    # 5. Упаковка
    dex_file = os.path.join(dex_dir, "classes.dex")
    if not os.path.exists(dex_file):
        raise BuildError("package", "classes.dex не создан — проверьте вывод d8")
    result = _run(["zip", "-q", "-j", unsigned, dex_file], "package")
    stages.append(_stage_entry(result, stat_size(unsigned)))

    # 6. zipalign (мягкий шаг)
    aligned = os.path.join(os.path.dirname(unsigned), "app.aligned.apk")
    if os.path.exists(zipalign):
        result = _run([zipalign, "-f", "4", unsigned, aligned], "zipalign")
        stages.append(_stage_entry(result, stat_size(aligned)))
    else:
        aligned = unsigned
        stages.append({"stage": "zipalign", "duration": 0.0, "size": None, "skipped": True})
        warnings.append(
            {
                "stage": "zipalign",
                "message": "zipalign не найден — APK не выровнен (v2-подпись это допускает)",
            }
        )

    # 7. Подпись
    suffix = "release" if release else "debug"
    final = output or os.path.join(project_dir, "build", "app-%s.apk" % suffix)
    os.makedirs(os.path.dirname(os.path.abspath(final)), exist_ok=True)
    shutil.copyfile(aligned, final)
    sign_warnings, keystore_kind = _sign(
        apksigner, final, project_dir, keystore, keystore_pass, key_alias
    )
    warnings.extend(sign_warnings)
    if release and keystore_kind == "debug":
        warnings.append(
            {
                "stage": "sign",
                "message": "--release с отладочным keystore: для публикации укажите --keystore",
            }
        )
    stages.append({"stage": "sign", "duration": 0.0, "size": stat_size(final)})

    store.save()
    return stages, warnings, final


def _find_kotlin_stdlib(kotlinc_bin):
    """Ищет kotlin-stdlib.jar рядом с kotlinc."""
    if not kotlinc_bin:
        return None
    root = os.path.dirname(os.path.dirname(kotlinc_bin))
    for candidate in (
        os.path.join(root, "lib", "kotlin-stdlib.jar"),
        os.path.join(root, "kotlinc", "lib", "kotlin-stdlib.jar"),
        os.path.join(root, "kotlinc", "lib", "kotlin-stdlib.jar"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _sign(apksigner, apk, project_dir, keystore, keystore_pass, key_alias):
    """Подписывает APK. Без keystore создаёт отладочный (с предупреждением)."""
    warnings = []
    ks = keystore or os.path.join(project_dir, ".debug.keystore")
    alias = key_alias or "debug"
    password = keystore_pass or "debugpass"

    keystore_kind = "explicit" if os.path.exists(ks) else "debug"
    if not os.path.exists(ks):
        _generate_keystore(ks, alias, password)
        warnings.append(
            {
                "stage": "sign",
                "message": "создан отладочный keystore %s — НЕ используйте для релиза" % ks,
            }
        )

    _run(
        [
            apksigner,
            "sign",
            "--ks",
            ks,
            "--ks-key-alias",
            alias,
            "--ks-pass",
            "pass:" + password,
            "--key-pass",
            "pass:" + password,
            apk,
        ],
        "sign",
    )
    _run([apksigner, "verify", apk], "sign")
    return warnings, keystore_kind


def _generate_keystore(path, alias, password):
    """Генерирует отладочный keystore через keytool."""
    keytool = shutil.which("keytool")
    if not keytool:
        raise BuildError("sign", "нет keytool — создайте keystore вручную")
    _run(
        [
            keytool,
            "-genkeypair",
            "-v",
            "-keystore",
            path,
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "10000",
            "-storepass",
            password,
            "-keypass",
            password,
            "-dname",
            "CN=builder-apk, O=Debug",
        ],
        "sign",
    )


def _skipped(stage):
    """Запись о стадии, пропущенной из-за кэша."""
    return {"stage": stage, "duration": 0.0, "size": None, "skipped": True, "cached": True}


def _stage_entry(result, size):
    return {"stage": result["stage"], "duration": round(result["duration"], 3), "size": size}


def _print_failure(report, error):
    print("ОШИБКА на стадии %s: %s" % (error.stage, error))
    if error.output:
        print("")
        print("--- вывод инструмента ---")
        print(error.output[-4000:])


def _print_success(report):
    print("Сборка %s" % report["project"])
    print("")
    print("%-15s %10s %12s" % ("стадия", "секунды", "размер"))
    for stage in report["stages"]:
        size = stage.get("size")
        if size:
            size_text = _human(size)
        elif stage.get("cached"):
            size_text = "из кэша"
        elif stage.get("skipped"):
            size_text = "пропущено"
        else:
            size_text = "-"
        print("%-15s %10.2f %12s" % (stage["stage"], stage["duration"], size_text))
    if report["warnings"]:
        print("")
        print("Предупреждения:")
        for warning in report["warnings"]:
            print("  ! [%s] %s" % (warning["stage"], warning["message"]))
    print("")
    print("APK: %s" % report["apk"])


def _human(num):
    if num is None:
        return "-"
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return ("%d %s" % (int(value), unit)) if unit == "B" else "%.1f %s" % (value, unit)
        value /= 1024
    return "%.1f GiB" % value