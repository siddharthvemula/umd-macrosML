// The day's macro totals as four progress rings (calories, protein, carbs, fat), each filling
// toward the student's goal. Display only: DashboardView loads the summary and the goals.

import MacroRing from './MacroRing.jsx'

const RINGS = [
  { key: 'calories', label: 'Calories', unit: '', tone: 'calories' },
  { key: 'protein_g', label: 'Protein', unit: 'g', tone: 'protein' },
  { key: 'carbs_g', label: 'Carbs', unit: 'g', tone: 'carbs' },
  { key: 'fat_g', label: 'Fat', unit: 'g', tone: 'fat' },
]

/**
 * Four rings for a day's totals against the daily goals.
 *
 * @param {{summary: {calories: number, protein_g: number, carbs_g: number, fat_g: number},
 *   goals: {calories: number, protein_g: number, carbs_g: number, fat_g: number}}} props
 *   summary: the object from getSummary(). goals: from loadGoals().
 * @returns {JSX.Element}
 * @example <MacroTotals summary={{ calories: 1840.5, protein_g: 92.3, carbs_g: 210, fat_g: 61.2 }} goals={DEFAULT_GOALS} />
 *   // rings: "1841 / 2000", "92g / 150g", "210g / 225g", "61g / 65g"
 */
export default function MacroTotals({ summary, goals }) {
  return (
    <ul className="macro-totals">
      {RINGS.map(({ key, label, unit, tone }) => (
        <MacroRing key={key} label={label} value={summary[key]} goal={goals[key]} unit={unit} tone={tone} />
      ))}
    </ul>
  )
}
