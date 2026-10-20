// The "Edit goals" form on the dashboard: four number boxes for the daily goals. Display
// only: it hands the typed values to onSave, and DashboardView saves them.

import { useState } from 'react'
import { cleanGoals } from '../goals.js'

const FIELDS = [
  { key: 'calories', label: 'Calories' },
  { key: 'protein_g', label: 'Protein (g)' },
  { key: 'carbs_g', label: 'Carbs (g)' },
  { key: 'fat_g', label: 'Fat (g)' },
]

/**
 * A small form for the four daily goals.
 *
 * Boxes start with the current goals. A box left empty or with a bad number keeps its
 * current goal (cleanGoals falls back to it), so one typo can't wipe out a goal.
 *
 * @param {{goals: object, onSave: (goals: object) => void, onCancel: () => void}} props
 * @returns {JSX.Element}
 * @example <GoalsForm goals={goals} onSave={handleSaveGoals} onCancel={() => setEditing(false)} />
 */
export default function GoalsForm({ goals, onSave, onCancel }) {
  // Kept as the typed strings, so a half-typed number ("") doesn't jump back while editing.
  const [values, setValues] = useState(() => Object.fromEntries(FIELDS.map(({ key }) => [key, String(goals[key])])))

  function handleSubmit(event) {
    // Stop the browser's default form submit, which would reload the page.
    event.preventDefault()
    onSave(cleanGoals(values, goals))
  }

  return (
    <form className="goals-form" onSubmit={handleSubmit} aria-label="Daily goals">
      <div className="goals-fields">
        {FIELDS.map(({ key, label }) => (
          <label key={key}>
            {label}
            <input
              type="number"
              inputMode="numeric"
              min="1"
              value={values[key]}
              onChange={(event) => setValues({ ...values, [key]: event.target.value })}
            />
          </label>
        ))}
      </div>
      <div className="goals-actions">
        <button type="button" className="button" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="button button--primary">
          Save goals
        </button>
      </div>
    </form>
  )
}
