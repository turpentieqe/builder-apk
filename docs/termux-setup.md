# Android SDK в Termux: что работает, а что нет

## Главная ловушка: архитектура

Официальные `cmdline-tools` и `build-tools` из Google собираются под **x86-64**.
На телефоне (aarch64) они не запускаются вообще:

```
$ ./aapt2 version
bash: ./aapt2: cannot execute binary file: Exec format error
```

Именно поэтому `builder-apk doctor` читает ELF-заголовок (`e_machine`) и пишет:

```
aapt2  BAD  ... собран под x86-64, а устройство aarch64 — запускать бесполезно
```

## Что поставить

```bash
pkg install openjdk-21 android-sdk
```

Тогда `aapt2`, `apksigner`, `zipalign` окажутся в `$PREFIX/bin` и будут
нативной сборки. `d8` отдельным бинарником не идёт — он лежит как
`build-tools/<ver>/lib/d8.jar` и запускается через `java -cp`.

`android.jar` (нужен для `aapt2 link` и `d8 --lib`) возьмите из
`platforms/android-34/android.jar` или укажите `--android-json` / `--sdk`.

## Kotlin

`kotlinc` в Termux-пакетах нет. Варианты:

1. Скачать `kotlin-compiler-*.zip` и распаковать — компилятор JVM-овский, он
   архитектурно-нейтрален, поэтому работает:
   ```bash
   unzip kotlin-compiler.zip -d ~/tools/kotlin
   export PATH="$HOME/tools/kotlin/kotlinc/bin:$PATH"
   ```
2. Или передать путь явно: `--kotlinc ~/tools/kotlin/kotlinc/bin/kotlinc`

`kotlinc` печатает в stderr страшную ошибку про `jansi` и `libc.so.6 not found` —
**это нормально**, на результат она не влияет. builder-apk превращает её в
аккуратное предупреждение.

## Переменные окружения

| Переменная | Что задаёт |
|---|---|
| `ANDROID_HOME` / `ANDROID_SDK_ROOT` | корень SDK; `doctor` и `build` сами найдут `build-tools/*` и `platforms/*` |
| `BUILD_TOOLS_VERSION` | какую версию build-tools использовать (по умолчанию берётся последняя) |