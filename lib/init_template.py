"""Скелет Android-проекта: генерация файлов для сборки без Gradle."""

import os
import shutil

import icon
import languages

MANIFEST_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{package}">

    <application
        android:label="{name}"
        android:icon="@mipmap/ic_launcher"
        android:allowBackup="true"
        android:supportsRtl="true">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

KOTLIN_TEMPLATE = """package {package}

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity : Activity() {{
    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        val label = TextView(this).apply {{
            text = "{name}"
            textSize = 24f
        }}
        setContentView(label)
    }}
}}
"""

JAVA_TEMPLATE = """package {package};

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public class MainActivity extends Activity {{
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        TextView label = new TextView(this);
        label.setText("{name}");
        label.setTextSize(24f);
        setContentView(label);
    }}
}}
"""

STRINGS_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{name}</string>
</resources>
"""

GROOVY_TEMPLATE = """package {package}

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity extends Activity {{
    @Override
    void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState)
        def label = new TextView(this)
        label.text = "{name}"
        label.textSize = 24f
        setContentView(label)
    }}
}}
"""

SCALA_TEMPLATE = """package {package}

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity extends Activity {{
  override def onCreate(savedInstanceState: Bundle): Unit = {{
    super.onCreate(savedInstanceState)
    val label = new TextView(this)
    label.setText("{name}")
    label.setTextSize(24f)
    setContentView(label)
  }}
}}
"""

BUILD_SH_TEMPLATE = """#!/usr/bin/env bash
# Сборка APK без Gradle: aapt2 -> (kotlinc|javac) -> d8 -> zip -> zipalign -> apksigner
# Сгенерировано builder-apk. Полная версия — `builder-apk build`.
set -euo pipefail

ANDROID_HOME="${{ANDROID_HOME:?задайте ANDROID_HOME}}"
BUILD_TOOLS_VERSION="${{BUILD_TOOLS_VERSION:-34.0.0}}"
BT="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VERSION"
ANDROID_JAR="$ANDROID_HOME/platforms/android-{target_sdk}/android.jar"
OUT_DIR="${OUT_DIR:-build}"
APK_NAME="${{APK_NAME:-{apk_name}.apk}}"

mkdir -p "$OUT_DIR/classes" "$OUT_DIR/dex"

if ! command -v builder-apk >/dev/null 2>&1; then
  echo "builder-apk не найден в PATH — используйте его: builder-apk build" >&2
fi

"$BT/aapt2" compile --dir res -o "$OUT_DIR/res.zip"
"$BT/aapt2" link -o "$OUT_DIR/app.unsigned.apk" \\
  -I "$ANDROID_JAR" \\
  --manifest AndroidManifest.xml \\
  "$OUT_DIR/res.zip" \\
  --min-sdk-version {min_sdk} \\
  --target-sdk-version {target_sdk} \\
  --version-code 1 \\
  --version-name 1.0

echo "[javac] компиляция Java"
javac -source 8 -target 8 \\
  -bootclasspath "$ANDROID_JAR" \\
  -d "$OUT_DIR/classes" \\
  src/{package_path}/MainActivity.java

echo "[d8] dex"
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \\
  --release --lib "$ANDROID_JAR" --min-api {min_sdk} \\
  --output "$OUT_DIR/dex" \\
  "$OUT_DIR"/classes/{package_path}/*.class

( cd "$OUT_DIR" && zip -q -j app.unsigned.apk dex/classes.dex && cp app.unsigned.apk "$APK_NAME" )
echo "Готово: $OUT_DIR/$APK_NAME"
"""

GITIGNORE_TEMPLATE = """build/
*.apk
*.keystore
.env
"""

KEYSTORE_WARNING = """# ВНИМАНИЕ: пароль от keyStore только для локальной отладки.
# Не коммитьте этот файл. Для релиза используйте свой keystore.

KS_PASS=changeit
KS_ALIAS=debug
"""

README_TEMPLATE = """# {name}

Скелет Android-проекта без Gradle, собранный `builder-apk init`.

## Сборка

```bash
builder-apk doctor        # проверить окружение
builder-apk build --release
```

APK появится в `build/{apk_name}.apk`.

## Структура

- `AndroidManifest.xml` — манифест
- `src/{package_path}/` — исходники ({lang})
- `res/values/strings.xml` — строки
- `build.sh` — эталонный скрипт ручной сборки
"""


def _package_path(package):
    return package.replace(".", "/")


def _activity_source(lang, base):
    """Возвращает (имя файла, содержимое) для MainActivity нужного языка."""
    templates = {
        "kotlin": ("MainActivity.kt", KOTLIN_TEMPLATE),
        "java": ("MainActivity.java", JAVA_TEMPLATE),
        "groovy": ("MainActivity.groovy", GROOVY_TEMPLATE),
        "scala": ("MainActivity.scala", SCALA_TEMPLATE),
    }
    if lang not in templates:
        raise SystemExit(
            "--lang должен быть один из: %s (получено: %s)" % (languages.supported_list(), lang)
        )
    filename, template = templates[lang]
    return filename, template.format(**base)


def scaffold(directory, name, package, lang="kotlin", min_sdk=21, target_sdk=34, force=False):
    """Создаёт скелет проекта. Возвращает список созданных путей."""
    if os.path.exists(directory) and not force and os.listdir(directory):
        raise SystemExit(
            "каталог %s не пуст (используйте --force, чтобы перезаписать)" % directory
        )

    package_path = _package_path(package)
    lang = (lang or "kotlin").lower()
    if lang not in languages.ALL_LANGUAGES:
        raise SystemExit(
            "--lang должен быть один из: %s (получено: %s)"
            % (languages.supported_list(), lang)
        )

    apk_name = (name or "app").lower().replace(" ", "-")
    base = {
        "name": name,
        "package": package,
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "apk_name": apk_name,
        "package_path": package_path,
        "lang": lang,
    }

    src_dir = os.path.join(directory, "src", package_path)
    res_dir = os.path.join(directory, "res", "values")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    files = {
        os.path.join(directory, "AndroidManifest.xml"): MANIFEST_TEMPLATE.format(**base),
        os.path.join(res_dir, "strings.xml"): STRINGS_TEMPLATE.format(**base),
        os.path.join(directory, ".gitignore"): GITIGNORE_TEMPLATE,
        os.path.join(directory, "README.md"): README_TEMPLATE.format(**base),
    }
    activity_file, activity_source = _activity_source(lang, base)
    files[os.path.join(src_dir, activity_file)] = activity_source

    created = []
    for path, content in files.items():
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        created.append(path)

    # Иконка обязательна: без неё aapt2 link падает на @mipmap/ic_launcher.
    created.extend(icon.write_icons(os.path.join(directory, "res")))
    return created


def keystore_warning():
    """Текст-предупреждение про пароль keyStore."""
    return KEYSTORE_WARNING