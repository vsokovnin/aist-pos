export const meta = {
  name: 'blind-derive-entry',
  description: 'Повторная слепая деривация под финальную семантику: только порог входа',
  phases: [{ title: 'Rederive', detail: '3 независимых агента на задачу' }],
}
// args: {jobs: [{id,title,short,promise}], catalog: [{id,title,levels}], hygiene: {level, caps, why}}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['job_id', 'operations', 'cells', 'gaps'],
  properties: {
    job_id: { type: 'string' },
    operations: { type: 'array', minItems: 2, items: { type: 'object', additionalProperties: false,
      required: ['name', 'input', 'output'],
      properties: { name: { type: 'string' }, input: { type: 'string' }, output: { type: 'string' } } } },
    cells: { type: 'array', minItems: 1, items: { type: 'object', additionalProperties: false,
      required: ['operation', 'cap_id', 'level', 'failure_scenario'],
      properties: { operation: { type: 'string' }, cap_id: { type: 'string' },
        level: { type: 'integer', minimum: 1, maximum: 5 },
        failure_scenario: { type: 'string', minLength: 40 } } } },
    gaps: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['operation', 'missing', 'failure_scenario'],
      properties: { operation: { type: 'string' }, missing: { type: 'string' },
        failure_scenario: { type: 'string', minLength: 40 } } } },
  },
}
const catalogText = args.catalog.map(c =>
  `- ${c.id} «${c.title}»\n` + [1, 2, 3, 4, 5].map(i => `  уровень ${i}: ${c.levels[String(i)]}`).join('\n')
).join('\n')
const prompt = (j) => `Ты аудитор модели зрелости. Задача руководителя, которую он хочет поручить ИИ-агенту:

«${j.title}» — ${j.short}
Обещание задачи: ${j.promise}

Каталог из ${args.catalog.length} способностей с уровнями 1-5 (ЗАКРЫТЫЙ словарь):
${catalogText}

Гигиена системы (${args.hygiene.caps.join(', ')}) заводится один раз на всю систему на уровне ${args.hygiene.level} и в ответе НЕ предлагается: ${args.hygiene.why}

Тебе нужен ТОЛЬКО ПОРОГ ВХОДА задачи — минимальный набор, при котором задача даёт ПЕРВУЮ РЕАЛЬНУЮ ЦЕННОСТЬ. Строго:
- порог входа — это «результат есть, и им можно пользоваться», а не «идеально» и не «безопасно»; риски на этом ярусе ДОПУСКАЮТСЯ;
- если без способности задача запускается и даёт пригодный первый результат, но эпизодически подводит, требует ручных подпорок или ломается в граничных случаях — это НЕ порог входа, не включай (это ярус зрелости);
- запуск по расписанию, накопление поверх прошлых прогонов, контроль сбоев, единая форма между прогонами — признаки зрелости, а не входа;
- проверяй себя контрпримером: опиши мысленно прогон без этой способности; получился пригодный результат — способность не пороговая.

Сделай три вещи.
1. Разложи задачу на наблюдаемые операции (шаги с входом и выходом).
2. Для каждой операции укажи способности каталога и МИНИМАЛЬНЫЙ уровень, без которого первой ценности нет. К каждой ячейке — сценарий отказа: «без способности X на уровне N результата нет или он непригоден, потому что…».
3. Операция не покрыта каталогом — не изобретай способность, фиксируй в gaps.

job_id="${j.id}".`
const runs = await parallel(args.jobs.flatMap(j =>
  [1, 2, 3].map(n => () =>
    agent(prompt(j), { label: `rederive:${j.id}#${n}`, phase: 'Rederive', schema: SCHEMA })
      .then(r => ({ ...r, agent_n: n })))))
return runs.filter(Boolean)
