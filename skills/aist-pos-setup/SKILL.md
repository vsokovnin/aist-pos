---
name: aist-pos-setup
description: /setup визард AIST POS. Интервью -> пишет aist-pos.config.yaml + ставит базу (9 Must: корневой файл, naming, git, граф-сторы, карта источников, память). Затем предлагает оценку.
---

# AIST POS — установка (setup)

Yar-style онбординг: из нуля до «уверенного L1» базы, поверх которой работают остальные скилы.
Читает `config/aist-pos.config.example.yaml`, `config/connectors.md`, шаблоны из `setup-templates/`.

## Когда запускать
- первый запуск после `git clone`; «настрой AIST POS», «/setup», «донастрой».

## Поток
1. **Интервью** (по одному вопросу, разговорно, на языке пользователя):
   - имя · роль · таймзона;
   - почта: gmail / outlook / нет;
   - календарь: gmail / outlook / нет;
   - мессенджер: telegram / нет;
   - транскрипты: granola / plaud / локально / нет;
   - выходная поверхность: file / telegram.
2. **Конфиг.** Скопируй `config/aist-pos.config.example.yaml` → `aist-pos.config.yaml` в рабочей папке пользователя и подставь ответы. Покажи итог, попроси подтвердить.
3. **База (9 Must плумбинг)** из `setup-templates/` — создай в рабочей папке, НЕ перезаписывая существующее:
   - корневой хаб-файл (`CLAUDE.md` или `AGENTS.md`) из `root-file.template.md` (подставь {{NAME}}/{{ROLE}}/{{TIMEZONE}}) — root_file + context_seed;
   - `naming-convention.md` из шаблона — naming;
   - `.gitignore` из `gitignore.template` + `git init` (если репо нет) + подсказка про авто-бэкап (3-2-1) — git;
   - сторы: `entities/{org,person,project}/` и `runtime/` — graph + capture sink (схема в `config/entities-schema.md`);
   - `source-map.md` из шаблона — source_map;
   - `memory.md` из шаблона — memory.
   - коннекторы: по ответам интервью подскажи, какие подключить в Claude Cowork/Code (по `config/connectors.md`) — авто-создать нельзя.
4. **Резюме.** Что создано/настроено и чего не хватает (неподключённые коннекторы).
5. **Дальше.** Предложи запустить `aist-pos-assess` (оценка зрелости) → план роста.

## Правила
- Идемпотентность: существующие файлы НЕ перезаписывать; предлагать merge/skip.
- Ничего вовне; только локальная рабочая папка пользователя.
- Портативность: ноль ссылок на чужую инфру; всё — из шаблонов и конфига репо.
