// Shows one day's menu, grouped by meal, with portion buttons on each dish. Display only:
// it gets the dishes and an onLog callback as props and never calls the API itself.

import { groupByMeal } from '../menu.js'
import PortionButtons from './PortionButtons.jsx'

/**
 * A hall's menu as sections (Breakfast, Lunch, ...) of dish rows.
 *
 * @param {{items: object[], loggingId: string|null, onLog: (item: object, servings: number) => void}} props
 *   items: dishes from getMenu(). loggingId: recipe_id currently being logged (its buttons are
 *   disabled). onLog: called when a portion button is clicked.
 * @returns {JSX.Element}
 * @example <MenuList items={menu.items} loggingId={null} onLog={handleLog} />
 */
export default function MenuList({ items, loggingId, onLog }) {
  if (items.length === 0) {
    return <p className="notice">No menu posted for today yet.</p>
  }

  return groupByMeal(items).map(({ meal, items: mealItems }) => (
    <section key={meal} className="meal">
      <h3>{meal}</h3>
      <ul className="dish-list">
        {mealItems.map((item) => (
          <DishRow
            key={item.recipe_id}
            item={item}
            isLogging={item.recipe_id === loggingId}
            onLog={(servings) => onLog(item, servings)}
          />
        ))}
      </ul>
    </section>
  ))
}

/**
 * One dish: name, station, the four macros per serving, and portion buttons.
 * Dishes with no nutrition get no buttons, since the API can't log macros it doesn't know.
 *
 * @param {{item: {name: string, station: string, nutrition: object|null}, isLogging: boolean,
 *   onLog: (servings: number) => void}} props
 * @returns {JSX.Element}
 */
function DishRow({ item, isLogging, onLog }) {
  const { nutrition } = item
  return (
    <li className={nutrition ? 'dish' : 'dish dish--no-data'}>
      <div>
        <span className="dish-name">{item.name}</span>
        <span className="dish-station">{item.station}</span>
      </div>
      <div className="dish-macros">
        <span>
          {nutrition
            ? `${Math.round(nutrition.calories)} cal · ${nutrition.protein_g}g protein · ` +
              `${nutrition.carbs_g}g carbs · ${nutrition.fat_g}g fat`
            : 'No nutrition info'}
        </span>
        {nutrition && <PortionButtons dishName={item.name} disabled={isLogging} onLog={onLog} />}
      </div>
    </li>
  )
}
