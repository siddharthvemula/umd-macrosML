// The "not listed? search today's menu" box on the photo screen. When the recognizer
// misses a dish, the student finds it here and logs it with the portion stepper; the
// photo screen links that log to the photo, which makes it a correction label for
// training. Display only: it gets the menu and an onLog callback, never calls the API.

import { useState } from 'react'
import { searchMenu } from '../menu.js'
import PortionStepper from './PortionStepper.jsx'

/**
 * A search box over today's menu, with a portion stepper on each match.
 *
 * @param {{items: object[], meal: string, excludeIds: string[], loggingId: string|null,
 *   onLog: (item: object, servings: number) => void}} props
 *   items: today's menu from getMenu(). meal: "" for the whole day.
 *   excludeIds: recipe IDs already shown as guesses, so they aren't listed twice.
 * @returns {JSX.Element}
 * @example <MenuSearch items={menu.items} meal="Lunch" excludeIds={['111*1']} loggingId={null} onLog={handleLog} />
 */
export default function MenuSearch({ items, meal, excludeIds, loggingId, onLog }) {
  const [query, setQuery] = useState('')
  const matches = searchMenu(items, query, { meal, excludeIds })

  return (
    <div className="menu-search">
      <label>
        Search today's menu{' '}
        <input type="search" value={query} placeholder="e.g. rice" onChange={(event) => setQuery(event.target.value)} />
      </label>
      {query.trim() && matches.length === 0 && <p className="notice">No dishes match "{query.trim()}".</p>}
      <ul className="dish-list">
        {matches.map((item) => (
          <li key={item.recipe_id} className="dish">
            <div className="dish-info">
              <span className="dish-name">{item.name}</span>
              <span className="dish-meta">{`${item.station} · ${Math.round(item.nutrition.calories)} cal per serving`}</span>
            </div>
            <PortionStepper
              dishName={item.name}
              nutrition={item.nutrition}
              disabled={item.recipe_id === loggingId}
              onLog={(servings) => onLog(item, servings)}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}
