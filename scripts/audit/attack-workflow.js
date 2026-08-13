export const meta = {
  name: 'attack-matrix',
  description: 'Состязательный пас: четыре атаки на порог входа каждой задачи + проверка яруса надёжности',
  phases: [{ title: 'Attack', detail: '5 атак на задачу, каждая своим вызовом' }],
}
// args: {jobs: [{job, title, promise, needs, hardens, trace, catalog}]}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['job_id', 'kind', 'attacks'],
  properties: {
    job_id: { type: 'string' },
    kind: { enum: ['missing', 'extra', 'too_low', 'too_high', 'hardens'] },
    attacks: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['cap_id', 'claim', 'evidence'],
        properties: {
          cap_id: { type: 'string' },
          claim: { type: 'string', minLength: 20 },
          evidence: { type: 'string', minLength: 60 },
        },
      },
    },
  },
}
const KINDS = {
  missing: 'Чего НЕ ХВАТАЕТ на пороге входа: какой способности нет в needs, хотя без неё задача не даст первой ценности вовсе (не «рискованно», а «результата нет»)? Дай сценарий отказа.',
  extra: 'Что ЛИШНЕЕ в needs: какая способность там стоит, хотя задача даст первую ценность и без неё? Докажи контрпримером — опиши прогон задачи без этой способности, где результат всё равно пригоден.',
  too_low: 'Где уровень ЗАНИЖЕН: какая ячейка needs стоит ниже, чем требует формулировка уровня для первой ценности? Покажи, что на текущем уровне пригодного результата не выходит.',
  too_high: 'Где уровень ЗАВЫШЕН: какая ячейка needs требует больше, чем нужно для ПЕРВОЙ ценности (требование зрелости выдаётся за порог входа)? Покажи, что на уровень ниже задача уже даёт пригодный результат.',
  hardens: 'Что пропущено на ЯРУСЕ НАДЁЖНОСТИ (hardens): чего не хватает в списке того, что делает задачу неподводящей? Только способности каталога, только со сценарием эпизодического отказа.',
}
const capText = (cat) => cat.map(c =>
  `- ${c.id} «${c.title}»: ур.3 — ${c.levels['3']}; ур.4 — ${c.levels['4']}; ур.5 — ${c.levels['5']}`).join('\n')
const out = await parallel(args.jobs.flatMap(j =>
  Object.keys(KINDS).map(kind => () =>
    agent(`Ты атакуешь матрицу зрелости AIST POS. Твой единственный вызов — ${kind}.

${KINDS[kind]}

Задача: «${j.title}»
Обещание: ${j.promise}
Порог входа (needs) — минимум, при котором задача ДАЁТ ПЕРВУЮ ЦЕННОСТЬ (риски допускаются): ${JSON.stringify(j.needs)}
Ярус надёжности (hardens) — чем задача перестаёт подводить: ${JSON.stringify(j.hardens || {})}
Гигиена системы (вне задач, уровень 3 на всю систему): сохранность, правило имён, карта конфиденциального — их в ответе НЕ предлагай.
Каноническая трасса задачи (операции и сценарии отказа):
${JSON.stringify(j.trace)}

Каталог способностей (уровни 3-5):
${capText(j.catalog)}

Правила: (1) не выдумывай атаку ради атаки — пустой список attacks это валидный и честный ответ; (2) каждая атака со сценарием отказа или контрпримером, «выглядит полезным» не аргумент; (3) различай пороги: порог входа ≠ надёжность ≠ гигиена; (4) job_id="${j.job}", kind="${kind}".`,
      { label: `attack:${kind}:${j.job}`, phase: 'Attack', schema: SCHEMA }))))
return out.filter(Boolean).filter(r => r.attacks && r.attacks.length)
