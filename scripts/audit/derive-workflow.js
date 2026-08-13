export const meta = {
  name: 'blind-derive',
  description: 'Слепая деривация задач: операции -> способности -> сценарии отказа',
  phases: [{ title: 'Derive', detail: '3 независимых агента на задачу' }],
}
// args: {jobs: [{id,title,short,promise}], catalog: [{id,title,levels}]}
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
  `- ${c.id} «${c.title}»\n` + [1, 2, 3, 4, 5].map(i => `  уровень ${i}: ${c.levels[i]}`).join('\n')
).join('\n')
const prompt = (j) => `Ты аудитор модели зрелости. Задача руководителя, которую он хочет поручить ИИ-агенту:

«${j.title}» — ${j.short}
Обещание задачи: ${j.promise}

Каталог из ${args.catalog.length} способностей с уровнями 1-5 (ЗАКРЫТЫЙ словарь):
${catalogText}

Сделай строго три вещи.
1. Разложи задачу на наблюдаемые операции (шаги с входом и выходом). Не абстракции: у каждого шага видно, что взяли и что получили.
2. Для каждой операции укажи, какие способности каталога и на каком МИНИМАЛЬНОМ уровне ей нужны. К каждой ячейке — сценарий отказа: «без способности X на уровне N этот шаг ломается вот так» — конкретно, с наблюдаемым последствием для руководителя. Уровень бери из формулировок каталога: требуемое поведение должно быть написано в формулировке этого уровня, не выше и не ниже.
3. Если операция не покрывается НИКАКОЙ способностью каталога — не изобретай новую, зафиксируй в gaps со сценарием отказа.

Правила: минимальность (не требуй уровень 4, если операции хватает 3); никаких способностей «на всякий случай» — только со сценарием отказа; job_id="${j.id}".`
const runs = await parallel(args.jobs.flatMap(j =>
  [1, 2, 3].map(n => () =>
    agent(prompt(j), { label: `derive:${j.id}#${n}`, phase: 'Derive', schema: SCHEMA })
      .then(r => ({ ...r, agent_n: n })))))
return runs.filter(Boolean)
