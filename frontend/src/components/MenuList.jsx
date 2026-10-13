// Shows one day's menu, grouped by meal. Display only: it gets the dishes as props and
// doesn't fetch anything, which keeps it simple to test.

import { groupByMeal } from '../menu.js'

/**
 * A hall's menu as sections (Breakfast, Lunch, ...) of dish rows.
 *
 * @param {{items: object[]}} props - Dishes from getMenu().
 * @returns {JSX.Element}
 * @example <MenuList items={menu.items} />
 */
export default function MenuList({ items }) {
  if (items.length === 0) {
    return <p className="notice">No menu posted for today yet.</p>
  }

  return groupByMeal(items).map(({ meal, items: mealItems }) => (
    <section key={meal} className="meal">
      <h2>{meal}</h2>
      <ul className="dish-list">
        {mealItems.map((item) => (
          <DishRow key={item.recipe_id} item={item} />
        ))}
      </ul>
    </section>
  ))
}

/**
 * One dish: its name and station, plus calories and protein per serving if we have them.
 *
 * @param {{item: {name: string, station: string, nutrition: object|null}}} props
 * @returns {JSX.Element}
 */
function DishRow({ item }) {
  const { nutrition } = item
  return (
    <li className={nutrition ? 'dish' : 'dish dish--no-data'}>
      <div>
        <span className="dish-name">{item.name}</span>
        <span className="dish-station">{item.station}</span>
      </div>
      <span className="dish-macros">
        {nutrition
          ? `${Math.round(nutrition.calories)} cal · ${nutrition.protein_g}g protein`
          : 'No nutrition info'}
      </span>
    </li>
  )
}
