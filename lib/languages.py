"""Реестр поддерживаемых языков исходников.

Один источник правды: какие расширения считаются исходниками, какие шаблоны
генерировать и как звать компилятор. Добавление языка = новая запись здесь
плюс шаблон в init_template.py — код сборки не трогаем.
"""

# Порядок важен: при смеси языков в src/ побеждает тот, кто выше.
LANGUAGES = {
    "kotlin": {
        "extension": ".kt",
        "label": "Kotlin",
        "compiler": "kotlinc",
        # kubectl-подобный поиск: в PATH или через --kotlinc
        "requires_compiler": True,
        "stdlib_glob": "kotlin-stdlib*.jar",
    },
    "java": {
        "extension": ".java",
        "label": "Java",
        "compiler": "javac",
        "requires_compiler": False,
        "stdlib_glob": None,
    },
    "groovy": {
        "extension": ".groovy",
        "label": "Groovy",
        "compiler": "groovyc",
        "requires_compiler": True,
        "stdlib_glob": "groovy-*.jar",
    },
    "scala": {
        "extension": ".scala",
        "label": "Scala",
        "compiler": "scalac",
        "requires_compiler": True,
        "stdlib_glob": "scala-library*.jar",
    },
}

# Языки, которые точно кладут классы в JVM (все наши) — d8 съест любой из них.
ALL_LANGUAGES = tuple(LANGUAGES)


def extension_for(lang):
    """Расширение файлов для языка."""
    return LANGUAGES[lang]["extension"]


def lang_for_extension(extension):
    """Обратный поиск: по расширению (.kt/.java/...) вернуть язык."""
    extension = extension if extension.startswith(".") else "." + extension
    for lang, info in LANGUAGES.items():
        if info["extension"] == extension:
            return lang
    return None


def label_for(lang):
    """Человеческое название языка."""
    return LANGUAGES.get(lang, {}).get("label", lang)


def supported_list():
    """Строка вида «kotlin, java, groovy» — для подсказок в ошибках."""
    return ", ".join(ALL_LANGUAGES)