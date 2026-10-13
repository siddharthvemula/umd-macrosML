// The day's macro totals as four tiles (calories, protein, carbs, fat). Display only:
// DashboardView loads the summary from the API and passes it in.

const TILES = [
  { key: 'calories', label: 'Calories', unit: '' },
  { key: 'protein_g', label: 'Protein', unit: 'g' },
  { key: 'carbs_g', label: 'Carbs', unit: 'g' },
  { key: 'fat_g', label: 'Fat', unit: 'g' },
]

/**
 * Four number tiles for a day's totals.
 *
 * @param {{summary: {calories: number, protein_g: number, carbs_g: number, fat_g: number}}} props
 *   summary: the object from getSummary().
 * @returns {JSX.Element}
 * @example <MacroTotals summary={{ calories: 1840.5, protein_g: 92.3, carbs_g: 210, fat_g: 61.2 }} />
 *   // tiles: "1841 Calories", "92g Protein", "210g Carbs", "61g Fat"
 */
export default function MacroTotals({ summary }) {
  return (
    <ul className="macro-totals">
      {TILES.map(({ key, label, unit }) => (
        <li key={key} className="macro-tile">
          {/* Whole numbers: a tenth of a gram is noise on a daily total. */}
          <span className="macro-value">{`${Math.round(summary[key])}${unit}`}</span>
          <span className="macro-label">{label}</span>
        </li>
      ))}
    </ul>
  )
}
