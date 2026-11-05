# Changelog

Все заметные изменения в проекте. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии — [SemVer](https://semver.org/lang/ru/).

## [0.1.0] — не выпущено

### Добавлено

- `builder-apk doctor` — проверка цепочки инструментов (java, aapt2, d8, kotlinc,
  zipalign, apksigner, android.jar) с версиями и подсказками по починке.
- Определение **архитектуры ELF** у инструментов: ловит x86-64 build-tools на
  ARM-устройстве (главная ловушка Termux).
- `builder-apk build` — сборка APK без Gradle:
  `aapt2 compile → aapt2 link → kotlinc/javac → d8 → zip → zipalign → apksigner`,
  с отчётом по времени и размеру каждой стадии.
- Никакая стадия не проваливается молча: код возврата, вывод инструмента и
  известные предупреждения (`jansi`, `UnsatisfiedLinkError`) попадают в отчёт.
- `zipalign` — мягкий шаг: его отсутствие даёт предупреждение, а не ошибку.
- `builder-apk init` — скелет проекта на **Kotlin и Java**, включая генерацию
  PNG-иконок во всех плотностях (без внешних зависимостей).
- `builder-apk inspect` — badging, разрешения, подпись и SHA-256 сертификата.
- `--json` для всех команд — пригодно для CI.
- Сборка debug/release с автоматическим отладочным keystore (с предупреждением).