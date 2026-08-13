export const meta = {
  name: 'consolidate-traces',
  description: 'Каноническая трасса: операции без дублей, ячейки ровно по финальной матрице',
  phases: [{ title: 'Consolidate' }],
}
// args: {jobs: [{job, title, needs, runs: [raw1, raw2, raw3], decisions: [n, ...]}]}
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['job_id', 'operations', 'cells', 'decisions'],
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
    decisions: { type: 'array', items: { type: 'integer' } },
  },
}
const out = await parallel(args.jobs.map(x => () =>
  agent(`Канонизируй трассу задачи «${x.title}». Состав и уровни ЗАФИКСИРОВАНЫ решениями аудита — не переоценивай их. Финальная матрица needs: ${JSON.stringify(x.needs)}. Номера решений: ${JSON.stringify(x.decisions)} — верни в decisions как есть.

Три независимых деривации (операции и ячейки со сценариями отказа):
${JSON.stringify(x.runs)}

Сделай: (1) слей операции трёх дериваций в один список без дублей — одинаковые по смыслу шаги объедини, имя выбери самое конкретное; (2) для КАЖДОЙ пары способность-уровень из needs выбери лучшую операцию и лучший сценарий отказа из дериваций; если уровень изменён решением и готового сценария под него нет — напиши сценарий сам, строго под формулировку этого уровня; (3) ячеек ровно столько, сколько пар в needs; job_id="${x.job}".`,
    { label: `consolidate:${x.job}`, phase: 'Consolidate', schema: SCHEMA })))
return out.filter(Boolean)
