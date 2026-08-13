export const meta = {
  name: 'judge-findings',
  description: 'Судья по каждой находке: подтверждается ли сценарий отказа',
  phases: [{ title: 'Judge' }],
}
// args: {findings: [...], jobs: {id: {title,short,promise}}, catalog: {cap_id: {title,levels}}}
const VERDICT = {
  type: 'object', additionalProperties: false, required: ['verdict', 'rationale'],
  properties: { verdict: { enum: ['CONFIRMED', 'REJECTED'] }, rationale: { type: 'string', minLength: 60 } },
}
const capText = (id) => {
  if (!id) return '(находка про дыру каталога — способности нет)'
  const c = args.catalog[id]
  return `«${c.title}»\n` + [1, 2, 3, 4, 5].map(i => `уровень ${i}: ${c.levels[i]}`).join('\n')
}
const CLS = {
  missing: 'агенты считают, что задаче нужна способность, которой нет в матрице',
  extra: 'способность есть в матрице, но ни один из трёх агентов её не вывел',
  level: 'преобладающий уровень агентов расходится с уровнем в матрице',
  gap: 'агент считает, что операция задачи не покрыта каталогом способностей',
}
const out = await parallel(args.findings.map(f => () => {
  const j = args.jobs[f.job_id]
  return agent(`Ты судья аудита модели зрелости. Единственный тест: подтверждается ли потребность СЦЕНАРИЕМ ОТКАЗА, согласующимся с обещанием задачи и формулировками уровней. Правдоподобие без сценария = REJECTED.

Задача: «${j.title}» — ${j.promise}
Класс находки: ${f.cls} — ${CLS[f.cls]}
Способность: ${capText(f.cap_id)}
Уровень в матрице: ${f.needs_level ?? '—'} · уровни агентов: ${JSON.stringify(f.levels_seen)} · голосов: ${f.votes}
Сценарии отказа от агентов:
${f.scenarios.map(s => '- ' + s).join('\n') || '- (нет — для extra это норма: способность не вывел никто)'}
${f.detail ? 'Деталь: ' + f.detail : ''}

Для missing/gap: CONFIRMED = хотя бы один сценарий показывает конкретную поломку задачи без этой способности. Для extra: CONFIRMED = способность действительно не нужна (попробуй сам построить сценарий отказа задачи без неё; построил убедительный — REJECTED с этим сценарием в rationale). Для level: CONFIRMED = уровень агентов обоснован формулировкой уровня лучше, чем уровень матрицы.`,
    { label: `judge:${f.n}:${f.job_id}/${f.cap_id ?? 'gap'}`, phase: 'Judge', schema: VERDICT })
    .then(v => ({ n: f.n, ...v }))
}))
return out.filter(Boolean)
