#!/usr/bin/env python3
"""builder-apk — сборка APK без Gradle (Termux/Linux).

Команды:
    builder-apk doctor              проверить цепочку инструментов
    builder-apk inspect <apk>       показать badging/подпись/размеры APK
    builder-apk init <dir>          сгенерировать скелет проекта
    builder-apk build [dir]         собрать APK
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(HERE, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import doctor  # noqa: E402
import inspector  # noqa: E402
import init_template  # noqa: E402
import builder  # noqa: E402


def _add_sdk_args(parser):
    parser.add_argument("--sdk", help="корень Android SDK (или $ANDROID_HOME)")
    parser.add_argument("--build-tools", help="каталог build-tools/<версия>")
    parser.add_argument("--android-jar", help="путь к android.jar")
    parser.add_argument("--kotlinc", help="путь к kotlinc")


def cmd_doctor(args):
    report = doctor.check_chain(
        build_tools=args.build_tools,
        android_jar=args.android_jar,
        java_bin=args.java or "java",
        kotlinc=args.kotlinc,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(doctor.format_report(report))
    return 1 if doctor.has_failures(report, extra_required=args.require or []) else 0


def cmd_inspect(args):
    data = inspector.inspect(args.apk)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(inspector.format_report(data))
    return 0


def cmd_init(args):
    created = init_template.scaffold(
        directory=args.directory,
        name=args.name,
        package=args.package,
        lang=args.lang,
        min_sdk=args.min_sdk,
        target_sdk=args.target_sdk,
    )
    for path in created:
        print("создан:", path)
    print("\nДальше: cd %s && builder-apk build" % args.directory)
    return 0


def cmd_build(args):
    return builder.build(
        project_dir=args.project_dir,
        sdk=args.sdk,
        build_tools=args.build_tools,
        android_jar=args.android_jar,
        kotlinc=args.kotlinc,
        release=args.release,
        output=args.output,
        json_output=args.json,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="builder-apk",
        description="Сборка Android APK без Gradle — прямо в Termux.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="проверить цепочку инструментов")
    _add_sdk_args(p_doctor)
    p_doctor.add_argument("--java", help="путь к java")
    p_doctor.add_argument("--require", action="append", help="считать инструмент обязательным")
    p_doctor.add_argument("--json", action="store_true", help="вывод в JSON")
    p_doctor.set_defaults(func=cmd_doctor)

    p_inspect = sub.add_parser("inspect", help="показать информацию об APK")
    p_inspect.add_argument("apk", help="путь к APK")
    p_inspect.add_argument("--json", action="store_true", help="вывод в JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    p_init = sub.add_parser("init", help="сгенерировать скелет проекта")
    p_init.add_argument("directory", help="каталог проекта")
    p_init.add_argument("--name", default="MyApp", help="название приложения")
    p_init.add_argument("--package", default="com.example.myapp", help="applicationId")
    p_init.add_argument("--lang", choices=("kotlin", "java"), default="kotlin")
    p_init.add_argument("--min-sdk", default=21, type=int)
    p_init.add_argument("--target-sdk", default=34, type=int)
    p_init.set_defaults(func=cmd_init)

    p_build = sub.add_parser("build", help="собрать APK")
    p_build.add_argument("project_dir", nargs="?", default=".", help="каталог проекта")
    _add_sdk_args(p_build)
    p_build.add_argument("--release", action="store_true", help="release-сборка (с подписью)")
    p_build.add_argument("--output", help="путь к выходному APK")
    p_build.add_argument("--json", action="store_true", help="вывод в JSON")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())