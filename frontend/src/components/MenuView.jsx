// The "today's menu" screen: a hall dropdown plus that hall's menu, where each dish can be
// logged. It owns the loading/error state and talks to the API; MenuList just draws what
// it's given.

import { useEffect, useState } from 'react'
import { getHalls, getMenu, logMeal } from '../api.js'
import MenuList from './MenuList.jsx'

/**
 * Loads the halls, then today's menu for whichever hall is selected, and logs dishes.
 *
 * @returns {JSX.Element}
 * @example <MenuView />
 */
export default function MenuView() {
  const [halls, setHalls] = useState([])
  const [hallId, setHallId] = useState(null)
  const [menu, setMenu] = useState(null)
  const [error, setError] = useState(null)
  // recipe_id of the dish being logged right now (its buttons are disabled), or null.
  const [loggingId, setLoggingId] = useState(null)
  // Result of the last log, shown as a banner: { ok: true/false, text: "..." }, or null.
  const [logResult, setLogResult] = useState(null)

  // Load the hall list once, when the screen first appears, and pick the first hall.
  useEffect(() => {
    getHalls()
      .then((loadedHalls) => {
        setHalls(loadedHalls)
        setHallId(loadedHalls[0]?.id ?? null)
      })
      .catch((err) => setError(err.message))
  }, [])

  // Reload the menu whenever the selected hall changes.
  useEffect(() => {
    if (!hallId) return
    // If the user switches halls before the old menu arrives, ignore the old answer,
    // otherwise a slow response could show the wrong hall's menu.
    let stale = false
    getMenu(hallId)
      .then((loadedMenu) => !stale && setMenu(loadedMenu))
      .catch((err) => !stale && setError(err.message))
    return () => {
      stale = true
    }
  }, [hallId])

  /**
   * Switches to another hall, clearing the old menu so "Loading…" shows while the new one loads.
   *
   * @param {string} newHallId - e.g. "yahentamitsi".
   */
  function selectHall(newHallId) {
    setMenu(null)
    setError(null)
    setHallId(newHallId)
  }

  /**
   * Logs some servings of a dish and reports how it went.
   *
   * @param {{recipe_id: string, name: string}} item - The dish from the menu.
   * @param {number} servings - e.g. 1.5.
   * @example handleLog(banana, 2)  // banner: "Logged 2x Banana (220 cal)."
   */
  async function handleLog(item, servings) {
    setLoggingId(item.recipe_id)
    try {
      const log = await logMeal(item.recipe_id, servings)
      // Use the server's calories (already multiplied by servings): it's what was saved.
      setLogResult({ ok: true, text: `Logged ${servings}x ${item.name} (${Math.round(log.calories)} cal).` })
    } catch (err) {
      setLogResult({ ok: false, text: `Couldn't log ${item.name}: ${err.message}` })
    } finally {
      setLoggingId(null)
    }
  }

  return (
    <div>
      <label className="hall-picker">
        Dining hall{' '}
        <select value={hallId ?? ''} onChange={(event) => selectHall(event.target.value)}>
          {halls.map((hall) => (
            <option key={hall.id} value={hall.id}>
              {hall.name}
            </option>
          ))}
        </select>
      </label>

      {error && <p className="notice notice--error">{error}</p>}
      {!error && !menu && <p className="notice">Loading menu…</p>}
      {logResult && (
        <p className={logResult.ok ? 'notice notice--success' : 'notice notice--error'} role="status">
          {logResult.text}
        </p>
      )}
      {menu && <MenuList items={menu.items} loggingId={loggingId} onLog={handleLog} />}
    </div>
  )
}
