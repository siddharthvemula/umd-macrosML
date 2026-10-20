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

/**
 * Groups one meal's dishes by station (Grill, Salad Bar, ...), for the menu's collapsible
 * sections. Stations keep the order the API listed them in, which is UMD's own order.
 *
 * @param {{station: string}[]} items - Dishes from one meal.
 * @returns {{station: string, items: object[]}[]} One group per station; dishes keep their order.
 * @example
 *   groupByStation([{ name: 'Burger', station: 'Grill' }, { name: 'Kale', station: 'Salad' }, { name: 'Fries', station: 'Grill' }])
 *   // -> [{ station: 'Grill', items: [Burger, Fries] }, { station: 'Salad', items: [Kale] }]
 */
export function groupByStation(items) {
  // A Map remembers insertion order, so stations come out in the order first seen.
  const groups = new Map()
  for (const item of items) {
    if (!groups.has(item.station)) groups.set(item.station, [])
    groups.get(item.station).push(item)
  }
  return [...groups.entries()].map(([station, stationItems]) => ({ station, items: stationItems }))
}

/**
 * Filters the menu screen's dishes by the search box: keeps dishes whose name or station
 * contains the text, ignoring case. Searching "grill" finds everything at the Grill.
 *
 * Unlike searchMenu (the photo screen's correction search), it keeps dishes without
 * nutrition and has no limit: it only narrows the full menu list.
 *
 * @param {{name: string, station: string}[]} items - Dishes from getMenu().
 * @param {string} query - What the user typed.
 * @returns {object[]} Matching dishes in menu order; all dishes for an empty query.
 * @example filterMenu(menu.items, 'RICE')  // -> [Spanish Rice, Sticky Rice, ...]
 */
export function filterMenu(items, query) {
  const text = query.trim().toLowerCase()
  if (!text) return items
  return items.filter(
    (item) => item.name.toLowerCase().includes(text) || item.station.toLowerCase().includes(text),
  )
}

/**
 * Finds dishes on a menu whose name contains the search text, for correcting the
 * photo recognizer ("not listed? search today's menu").
 *
 * Only dishes that can be logged (they have nutrition) are returned, each recipe once
 * (UMD lists some dishes at several stations), skipping dishes already shown as guesses.
 *
 * @param {object[]} items - Dishes from getMenu(), each with name, recipe_id, meal, nutrition.
 * @param {string} query - What the user typed; matched anywhere in the name, ignoring case.
 * @param {{meal?: string, excludeIds?: string[], limit?: number}} [options]
 *   meal: only this meal ("" or left out = whole day). excludeIds: recipe IDs to skip.
 *   limit: at most this many results (default 8, enough to fit on a phone screen).
 * @returns {object[]} Matching dishes in menu order; [] for an empty query.
 * @example
 *   searchMenu(menu.items, 'rice', { meal: 'Lunch' })  // -> [{ name: 'Spanish Rice', ... }]
 */
export function searchMenu(items, query, { meal = '', excludeIds = [], limit = 8 } = {}) {
  const text = query.trim().toLowerCase()
  if (!text) return []

  const seen = new Set(excludeIds)
  const matches = []
  for (const item of items) {
    if (matches.length === limit) break
    if (seen.has(item.recipe_id) || !item.nutrition) continue
    if (meal && item.meal.toLowerCase() !== meal.toLowerCase()) continue
    if (!item.name.toLowerCase().includes(text)) continue
    seen.add(item.recipe_id)
    matches.push(item)
  }
  return matches
}
