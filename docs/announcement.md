<!-- НЕ релиз-анонс, а черновик. Опубликуйте с аккаунта, которому доверяете. -->

## Что это

`builder-apk` — сборка Android APK **без Gradle**, прямо в Termux.

```bash
builder-apk doctor      # проверить окружение
builder-apk init myapp  # скелет: Kotlin или Java
builder-apk build       # APK за секунды
```

Внутри — обычная ручная цепочка, автоматизированная по шагам:

```
aapt2 compile → aapt2 link → kotlinc/javac → d8 → zip → zipalign → apksigner
```

Никаких зависимостей: только `python3` и стандартная библиотека.

## Зачем

Если вы когда-нибудь пробовали Gradle в Termux, вы знаете: демоны, гигабайты памяти, сборки по несколько минут, и всё это с шансом упасть на `OutOfMemoryError`. Для маленького приложения это не нужно.

Ручной скрипт тоже не вариант — он **проваливается молча**. Мой первый скрипт:

```
[3/6] kotlinc (компиляция Kotlin)
Failed to load native library:jansi-... libjansi.so
java.lang.UnsatisfiedLinkError: library "libc.so.6" not found
```

⚠️ **И после этой ошибки сборка шла дальше и «успешно» завершалась** — потому что `set -e` не ловит stderr. Так я узнал, что «зелёная» сборка ничего не значит.

`builder-apk` делает так, чтобы это было невозможно.

## Что реально ловит

Всё ниже — грабли, на которые я наступил лично:

**1. x86-64 SDK на ARM-телефоне**

Официальные build-tools собираются под x86-64. На телефоне:

```
$ ./aapt2 version
cannot execute binary file: Exec format error
```

`doctor` читает ELF-заголовок и говорит прямо:

```
aapt2  BAD  ... собран под x86-64, а устройство aarch64 — запускать бесполезно
```

А `build` в этом случае берёт рабочий бинарник из `$PATH`.

**2. Иконка, которой нет**

Манифест с `@mipmap/ic_launcher`, а ресурса нет → `aapt2 link` падает с невнятным `resource mipmap/ic_launcher not found`. `init` сразу генерирует PNG во всех плотностях (zlib, без Pillow).

**3. `apksigner` в Termux говорит иначе**

`inspect` показывал «Подписи нет» на нормально подписанном APK — версия из Termux печатает `V3.0 Signer: certificate DN:` вместо `Verified using v3 scheme`.

**4. Молчаливые провалы**

Каждая стадия проверяется: код возврата, вывод, и известные «шумные» предупреждения попадают в отчёт, а не теряются.

## Проверено вживую

Собрано на телефоне (Termux, aarch64, Android 16, build-tools 34):

| Проект | Стадии | Результат |
|---|---|---|
| Java из `init` | 7/7 | 12.7 KiB APK, подпись OK |
| Kotlin из `init` | 7/7 | 604.7 KiB APK, подпись OK |

## Чего не умеет

Честно: только Kotlin и Java. Нет NDK/C++, нет Compose, нет мульти-модульных проектов, нет AAB для Google Play, нет инкрементальной сборки. Это не замена Gradle — это замена «написать build.sh руками для маленького проекта на телефоне».

## Ссылки

- Репозиторий: https://github.com/turpentieqe/builder-apk
- Документация по Termux: https://github.com/turpentieqe/builder-apk/blob/main/docs/termux-setup.md
- 57 тестов, SDK для них не нужен: `python3 tests/run.py`

Есть задачи для контрибьюторов — метка `good first issue`.

Спасибо, что дочитали. Буду рад багрепортам от тех, у кого другая раскладка SDK — особенно интересно, что происходит на x86-64 эмуляторах.