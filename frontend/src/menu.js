// Display helpers for menus. The API returns a flat list of dishes (each with its meal);
// grouping them for the screen is the frontend's job (see DECISIONS.md, Backend API).

// The order meals happen in a day. Anything else UMD adds goes after these.
const MEAL_ORDER = ['Breakfast', 'Brunch', 'Lunch', 'Dinner']

/**
 * Groups a menu's dishes by meal, in the order the meals happen in a day.
 *
 * @param {{meal: string}[]} items - Dishes from getMenu(), in the API's order.
 * @returns {{meal: string, items: object[]}[]} One group per meal; dishes keep their order.
 * @example
 *   groupByMeal([{ name: 'Pizza', meal: 'Dinner' }, { name: 'Eggs', meal: 'Breakfast' }])
 *   // -> [{ meal: 'Breakfast', items: [Eggs] }, { meal: 'Dinner', items: [Pizza] }]
 */
export function groupByMeal(items) {
  const groups = new Map()
  for (const item of items) {
    if (!groups.has(item.meal)) groups.set(item.meal, [])
    groups.get(item.meal).push(item)
  }
  return [...groups.entries()]
    .map(([meal, mealItems]) => ({ meal, items: mealItems }))
    .sort((a, b) => mealRank(a.meal) - mealRank(b.meal))
}

/**
 * Where a meal goes in the day; unknown meals rank after the known ones.
 *
 * @param {string} meal - e.g. "Lunch".
 * @returns {number} e.g. 2 for "Lunch", MEAL_ORDER.length for an unknown meal.
 */
function mealRank(meal) {
  const index = MEAL_ORDER.indexOf(meal)
  return index === -1 ? MEAL_ORDER.length : index
}
