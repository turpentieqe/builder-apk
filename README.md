# builder-apk

Сборка Android APK **без Gradle** — прямо в Termux (или на любом Linux).

```bash
builder-apk doctor      # проверить, что цепочка инструментов на месте
builder-apk init myapp  # сгенерировать скелет проекта (Kotlin или Java)
builder-apk build       # собрать APK
builder-apk inspect app-debug.apk
```

## Зачем

Gradle в Termux — это демоны, гигабайты памяти и сборки по несколько минут.
Но для простого приложения он и не нужен: APK собирается руками за семь шагов.

```
aapt2 compile → aapt2 link → kotlinc/javac → d8 → zip → zipalign → apksigner
```

`builder-apk` автоматизирует именно эту цепочку и — что важнее — **не даёт ей
провалиться молча**.

## Что он ловит (и почему это важно)

Всё ниже — реальные грабли, на которые наступают в Termux:

| Грабли | Что делает builder-apk |
|---|---|
| В распакованном SDK лежат **x86-64** бинарники, а телефон — aarch64 | `doctor` читает ELF-заголовок и говорит прямо: «собран под x86-64, а устройство aarch64»; `build` в этом случае берёт рабочий бинарник из `$PATH` |
| `kotlinc` роняет `jansi`, но сборка «зелёная» | предупреждение выносится в отчёт, а не теряется в stderr |
| `zipalign` вообще нет | мягкий шаг: сборка идёт дальше, в отчёте `WARN` (v2-подпись это допускает) |
| В манифесте `@mipmap/ic_launcher`, а ресурса нет | `init` сразу генерирует PNG-иконки во всех плотностях |
| Пароль keystore в репозитории | `init` кладёт keystore в `.gitignore`; без явного keystore создаётся отладочный с предупреждением |
| Стадия упала, а сообщение потерялось | показывается стадия, код возврата и последние строки вывода инструмента |

## Установка

Нужен только `python3` (>= 3.8) и Android SDK build-tools.

```bash
git clone https://github.com/turpentieqe/builder-apk.git
ln -s "$PWD/builder-apk/bin/builder-apk" "$PREFIX/bin/builder-apk"   # Termux
# или: ln -s "$PWD/builder-apk/bin/builder-apk" /usr/local/bin/builder-apk
```

В Termux сам SDK проще всего поставить пакетом:

```bash
pkg install openjdk-21 android-sdk
export ANDROID_HOME="$PREFIX/opt/android-sdk"
```

Для Kotlin добавьте `kotlinc` в `$PATH` или передайте `--kotlinc /path/to/kotlinc`.

## Команды

### `doctor`

```
$ builder-apk doctor
Инструмент       Статус  Версия         Путь
java             OK      21.0.13        /data/data/com.termux/files/usr/bin/java
aapt2            OK      2.20           /data/data/com.termux/files/usr/bin/aapt2
d8               OK      -              .../build-tools/34.0.0/lib/d8.jar
kotlinc          MISS    -              -
zipalign         OK      -              /data/data/com.termux/files/usr/bin/zipalign
apksigner        OK      0.9            /data/data/com.termux/files/usr/bin/apksigner
android_jar      OK      -              .../platforms/android-34/android.jar
```

`--require kotlinc` поднимает инструмент до обязательного (полезно в CI).
`--json` — для машинной обработки.

### `init`

```bash
builder-apk init myapp --name "Моё приложение" --package com.me.myapp --lang java
builder-apk init myapp --lang kotlin --min-sdk 24 --target-sdk 34
```

Создаёт: `AndroidManifest.xml`, `res/values/strings.xml`, PNG-иконки в
`mipmap-mdpi…xxhdpi`, `src/…/MainActivity.{kt,java}`, `.gitignore`, `README.md`.

### `build`

```bash
export ANDROID_HOME=$HOME/android-sdk
builder-apk build                 # debug
builder-apk build --release --keystore ~/keys/release.keystore
builder-apk build --json          # машинный вывод для CI
```

Отчёт по стадиям:

```
стадия             секунды       размер
aapt2-compile         0.03      2.3 KiB
aapt2-link            0.18      3.5 KiB
compile               6.72            -
d8                    9.19      1.9 MiB
package               0.11    598.1 KiB
zipalign              0.01    598.2 KiB
sign                  0.00    604.7 KiB
```

### `inspect`

Пакет, версия, min/target SDK, launchable-activity, разрешения, подпись и SHA-256
сертификата — в одном экране.

## Тесты

```bash
python3 tests/run.py
```

57 тестов, без внешних зависимостей: стадии вызываются на фейковых
исполняемых скриптах, поэтому SDK для тестов не нужен.

## Ограничения

- Только Kotlin и Java. C/C++ (NDK), Compose, мульти-модульные проекты — нет.
- Нет инкрементальной сборки: каждый запуск собирает всё заново.
- Нет работы с AAB, не поддерживаются build variants и flavors.
- Тестировалось на Termux (aarch64) и Linux x86-64.

## Лицензия

MIT