// Shows one day's menu: a search box, then each meal (Breakfast, Lunch, ...) split into
// collapsible station sections (Grill, Salad Bar, ...), with portion buttons on each dish.
// It never calls the API: it gets the dishes and an onLog callback as props. The search text
// is its own state, since only this screen uses it.

import { useId, useState } from 'react'
import { filterMenu, groupByMeal, groupByStation } from '../menu.js'
import PortionStepper from './PortionStepper.jsx'

/**
 * A hall's menu: search box, meal headings, collapsible stations, dish rows.
 *
 * @param {{items: object[], loggingId: string|null, onLog: (item: object, servings: number) => void}} props
 *   items: dishes from getMenu(). loggingId: recipe_id currently being logged (its buttons are
 *   disabled). onLog: called when a portion button is clicked.
 * @returns {JSX.Element}
 * @example <MenuList items={menu.items} loggingId={null} onLog={handleLog} />
 *   // typing "rice" leaves only the rice dishes, with their stations opened
 */
export default function MenuList({ items, loggingId, onLog }) {
  const [query, setQuery] = useState('')
  // A unique id ties the hidden label to the input, even if two menus were ever on screen.
  const searchId = useId()

  if (items.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">📋</span>
        <p className="empty-state-title">No menu posted for today yet.</p>
        <p className="empty-state-hint">UMD usually posts menus a few days ahead. Try the other dining hall.</p>
      </div>
    )
  }

  const isSearching = query.trim() !== ''
  const matches = filterMenu(items, query)

  return (
    <>
      <label className="visually-hidden" htmlFor={searchId}>
        Search dishes
      </label>
      <input
        id={searchId}
        className="menu-filter"
        type="search"
        value={query}
        placeholder="Search dishes or stations"
        onChange={(event) => setQuery(event.target.value)}
      />
      {/* role="status" makes screen readers announce the new count as the student types. */}
      {isSearching && (
        <p className="menu-filter-count" role="status">
          {matches.length === 0
            ? `No dishes match "${query.trim()}".`
            : `${matches.length} ${matches.length === 1 ? 'dish matches' : 'dishes match'}`}
        </p>
      )}

      {groupByMeal(matches).map(({ meal, items: mealItems }) => (
        <section key={meal} className="meal">
          <h3>{meal}</h3>
          {groupByStation(mealItems).map(({ station, items: stationItems }) => (
            // <details> is the browser's own collapsible box (no state needed). Stations start
            // closed so the menu fits on a phone; while searching, every station with a match
            // opens. The key includes isSearching so clearing the search closes them again.
            <details key={`${station}-${isSearching}`} className="station" open={isSearching}>
              <summary>
                <span className="station-name">{station}</span>
                <span className="station-count">{stationItems.length}</span>
              </summary>
              <ul className="dish-list">
                {stationItems.map((item) => (
                  <DishRow
                    key={item.recipe_id}
                    item={item}
                    isLogging={item.recipe_id === loggingId}
                    onLog={(servings) => onLog(item, servings)}
                  />
                ))}
              </ul>
            </details>
          ))}
        </section>
      ))}
    </>
  )
}

/**
 * One dish: the name and serving size, then the portion stepper with live macros. Dishes with
 * no nutrition say so and get no stepper, since the API can't log macros it doesn't know.
 *
 * @param {{item: {name: string, nutrition: object|null}, isLogging: boolean,
 *   onLog: (servings: number) => void}} props
 * @returns {JSX.Element}
 */
function DishRow({ item, isLogging, onLog }) {
  const { nutrition } = item
  return (
    <li className={nutrition ? 'dish' : 'dish dish--no-data'}>
      <div className="dish-info">
        <span className="dish-name">{item.name}</span>
        {/* With nutrition, the stepper below shows the macros (live for the chosen amount). */}
        {!nutrition && <span className="dish-meta">No nutrition info</span>}
        {nutrition?.serving_size && <span className="dish-serving">{`1 serving = ${nutrition.serving_size}`}</span>}
      </div>
      {nutrition && <PortionStepper dishName={item.name} nutrition={nutrition} disabled={isLogging} onLog={onLog} />}
    </li>
  )
}
