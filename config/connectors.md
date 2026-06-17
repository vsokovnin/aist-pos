# Connector-map — абстрактный коннектор → конкретная интеграция

Скилы НИКОГДА не вызывают интеграцию по имени напрямую. Они читают `connectors.*` из
`aist-pos.config.yaml` и резолвят по этой таблице. Это единственное место с именами интеграций —
так скилы остаются портативными между Claude Cowork и Claude Code.

| Абстракция | Значение конфига | Cowork Connector | Claude Code (MCP / утилита) |
|---|---|---|---|
| email | gmail | Gmail | `mcp__claude_ai_Gmail__*` |
| email | outlook | Microsoft 365 | `mcp__plugin_legal_ms365__*` |
| calendar | gmail | Google Calendar | `mcp__claude_ai_Google_Calendar__*` |
| calendar | outlook | Microsoft 365 | `mcp__plugin_legal_ms365__*` |
| messenger | telegram | Telegram | `Tech/tg-userbot` (send_to_saved / read) |
| transcripts | granola/plaud/local | — (локальные файлы) | папка `stores`-уровня / ингест-скил |
| (любой) | none | — | источник пропускается (fail-soft, см. правило ниже) |
| (вывод) output_surface=file | — | запись в `stores.brief` / `stores.tasks` | то же |
| (вывод) output_surface=telegram | Telegram | Telegram | `Tech/tg-userbot` |

**Правило деградации:** если `connectors.X = none` или коннектор недоступен — скил не падает, а
работает по доступным источникам и явно помечает, что пропущено (fail-soft, не fail-loud).
**Auth:** если коннектор сконфигурен, но не авторизован — скил говорит «нужно подключить <X>» и
продолжает по остальным.

## Доступ по планам (важно)
- **Google Workspace** — все планы (вплоть до Free) по личному OAuth; единственный коннектор с реальной записью (Calendar: создание/перенос; Gmail: только черновики, без отправки; Drive: только создание нового файла). Рекомендованный дефолт для индивидуального пользователя.
- **Microsoft 365** — только Team/Enterprise + права Global Admin в Microsoft Entra; **read-only** (создавать/отправлять нельзя). Для приватности — local connector.
- На экране OAuth можно выбрать read-only либо read-write скоуп; начните с минимального и расширьте при необходимости.
