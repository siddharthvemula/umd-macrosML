// Portion math for the − / + stepper: the allowed range, stepping, and the macros for a
// chosen amount. Pure functions, so they're tested without rendering anything.

export const MIN_SERVINGS = 0.5
export const MAX_SERVINGS = 3
export const SERVINGS_STEP = 0.25

/**
 * Move a serving amount one step up or down, staying within 0.5x–3x.
 *
 * @param {number} servings - current amount, e.g. 1
 * @param {number} direction - +1 for "+", -1 for "−"
 * @returns {number} the new amount
 * @example stepServings(1, +1)  // -> 1.25
 * @example stepServings(3, +1)  // -> 3 (already at the top)
 */
export function stepServings(servings, direction) {
  const next = servings + direction * SERVINGS_STEP
  return Math.min(MAX_SERVINGS, Math.max(MIN_SERVINGS, next))
}

/**
 * Label a serving amount: "1x", "1.25x", "0.75x".
 *
 * @param {number} servings
 * @returns {string}
 * @example formatServings(1.5)  // -> "1.5x"
 */
export function formatServings(servings) {
  // Multiples of 0.25 are exact in binary, so String() never shows 1.2499999.
  return `${servings}x`
}

/**
 * The calories and macros for a chosen amount, rounded for display (whole calories,
 * grams to 1 decimal).
 *
 * @param {{calories: number, protein_g: number, carbs_g: number, fat_g: number}} nutrition - per serving
 * @param {number} servings
 * @returns {string} e.g. "275 cal · 17.5g protein · 25g carbs · 15g fat"
 * @example macrosFor({calories: 220, protein_g: 14, carbs_g: 20, fat_g: 12}, 1.25)
 *   // -> "275 cal · 17.5g protein · 25g carbs · 15g fat"
 */
export function macrosFor(nutrition, servings) {
  const grams = (value) => Math.round(value * servings * 10) / 10
  return (
    `${Math.round(nutrition.calories * servings)} cal · ${grams(nutrition.protein_g)}g protein · ` +
    `${grams(nutrition.carbs_g)}g carbs · ${grams(nutrition.fat_g)}g fat`
  )
}
