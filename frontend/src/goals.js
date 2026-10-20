// The student's daily macro goals, which the dashboard rings fill toward. Kept in
// localStorage (like the device ID and the privacy notice), not on the server: goals are
// a personal display setting, and keeping them here needs no backend change.

const GOALS_KEY = 'macros.goals'

// A typical active college student's day. Students change these in the app.
export const DEFAULT_GOALS = Object.freeze({ calories: 2000, protein_g: 150, carbs_g: 225, fat_g: 65 })

// Above this, a typed goal is almost surely a typo (an extra zero), not a real target.
const MAX_GOAL = 20000

/**
 * Turns any object into a complete, valid set of goals.
 *
 * Each goal must be a positive number up to MAX_GOAL; anything else (missing, text,
 * zero, negative) falls back to the matching value in `fallback`. Goals are whole numbers.
 *
 * @param {object|null} raw - e.g. saved JSON, or what the student typed.
 * @param {object} [fallback] - Used for each goal that isn't valid. Defaults to DEFAULT_GOALS.
 * @returns {{calories: number, protein_g: number, carbs_g: number, fat_g: number}}
 * @example cleanGoals({ calories: '2500', protein_g: -3 })
 *   // -> { calories: 2500, protein_g: 150, carbs_g: 225, fat_g: 65 }
 */
export function cleanGoals(raw, fallback = DEFAULT_GOALS) {
  const goals = {}
  for (const key of Object.keys(DEFAULT_GOALS)) {
    // Inputs give strings ("2500"); Number() turns "" and junk into 0 or NaN, both rejected below.
    const value = Number(raw?.[key])
    goals[key] = Number.isFinite(value) && value > 0 && value <= MAX_GOAL ? Math.round(value) : fallback[key]
  }
  return goals
}

/**
 * Reads the saved goals, or the defaults if none are saved (or storage is blocked).
 *
 * @returns {{calories: number, protein_g: number, carbs_g: number, fat_g: number}}
 * @example loadGoals()  // -> { calories: 2000, protein_g: 150, carbs_g: 225, fat_g: 65 } on first visit
 */
export function loadGoals() {
  try {
    // JSON.parse(null) is null, which cleanGoals turns into the defaults.
    return cleanGoals(JSON.parse(window.localStorage.getItem(GOALS_KEY)))
  } catch {
    // Blocked storage or corrupted JSON: the defaults still give the rings something to fill.
    return { ...DEFAULT_GOALS }
  }
}

/**
 * Saves goals for next time and returns the cleaned version that was saved.
 *
 * @param {object} goals - e.g. { calories: 2500, protein_g: 180, carbs_g: 250, fat_g: 70 }.
 * @returns {{calories: number, protein_g: number, carbs_g: number, fat_g: number}}
 * @example saveGoals({ calories: 2500, protein_g: 180, carbs_g: 250, fat_g: 70 })
 */
export function saveGoals(goals) {
  const clean = cleanGoals(goals)
  try {
    window.localStorage.setItem(GOALS_KEY, JSON.stringify(clean))
  } catch {
    // Blocked storage: the new goals still apply until the page is reloaded.
  }
  return clean
}
