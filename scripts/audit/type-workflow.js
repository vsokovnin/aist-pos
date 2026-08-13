export const meta = {
  name: 'type-findings',
  description: 'Типизация подтверждённых находок по трём ярусам: вход / надёжность / гигиена',
  phases: [{ title: 'Type', detail: 'один агент на находку, по сценариям отказа' }],
}
// args: {findings: [{n, cls, job_id, job_title, job_promise, cap_id, cap_title, cap_levels|null,
//                    needs_level, levels_seen, detail, scenarios, judge_rationale}]}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['n', 'tier', 'rationale'],
  properties: {
    n: { type: 'integer' },
    tier: { enum: ['entry', 'reliability', 'hygiene'] },
    rationale: { type: 'string', minLength: 60 },
  },
}
const capText = (f) => {
  if (!f.cap_id) return '(находка про дыру каталога: ' + (f.detail || '') + ')'
  return `«${f.cap_title}»\n` + [1, 2, 3, 4, 5]
    .map(i => `уровень ${i}: ${f.cap_levels[i]}`).join('\n')
}
const out = await parallel(args.findings.map(f => () =>
  agent(`Ты типизируешь подтверждённую находку аудита модели зрелости по ТРЁМ ярусам. Читай сценарии отказа буквально: что именно в них ломается?

- entry (порог входа): без этой способности на этом уровне задача НЕ ДАЁТ первой ценности — результата нет вовсе или он непригоден с первого же запуска. Не «рискован», а «нет результата».
- reliability (надёжность/зрелость): задача запускается и даёт ценность без этого, но эпизодически подводит, требует ручных подпорок или перепроверок, ломается в граничных случаях; сюда же — «зрелые обещания» задачи (накопление поверх прошлого, запуск по расписанию, защита от редких сбоев).
- hygiene (гигиена системы): отказ не специфичен этой задаче — тот же сценарий (потеря данных, утечка конфиденциального, бардак в файлах) бьёт ЛЮБУЮ задачу с файлами и данными; защита ставится один раз на систему, а не в каждую задачу.

Задача: «${f.job_title}» — ${f.job_promise}
Класс находки: ${f.cls}${f.needs_level ? ' · уровень в матрице: ' + f.needs_level : ''}${f.levels_seen && f.levels_seen.length ? ' · уровни агентов: ' + JSON.stringify(f.levels_seen) : ''}
Способность: ${capText(f)}
Сценарии отказа:
${(f.scenarios || []).map(s => '- ' + s).join('\n') || '- (нет)'}
Обоснование судьи: ${f.judge_rationale}

Выбери РОВНО один ярус. Тест на entry строгий: спроси себя «запустится ли задача и принесёт ли пригодный первый результат БЕЗ этого?» — если да, это не entry. Тест на hygiene: «останется ли сценарий отказа, если заменить эту задачу любой другой?» — если да, это hygiene. Верни n=${f.n}.`,
    { label: `type:${f.n}:${f.job_id}/${f.cap_id ?? 'gap'}`, phase: 'Type', schema: SCHEMA })))
return out.filter(Boolean)
