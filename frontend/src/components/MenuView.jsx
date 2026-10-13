// The "today's menu" screen: a hall dropdown plus that hall's menu. It owns the loading
// and error state and fetches from the API; MenuList just draws what it's given.

import { useEffect, useState } from 'react'
import { getHalls, getMenu } from '../api.js'
import MenuList from './MenuList.jsx'

/**
 * Loads the halls, then today's menu for whichever hall is selected.
 *
 * @returns {JSX.Element}
 * @example <MenuView />
 */
export default function MenuView() {
  const [halls, setHalls] = useState([])
  const [hallId, setHallId] = useState(null)
  const [menu, setMenu] = useState(null)
  const [error, setError] = useState(null)

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
      {menu && <MenuList items={menu.items} />}
    </div>
  )
}
