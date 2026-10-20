// The "today's menu" screen: one hall's menu, where each dish can be logged. It owns the
// loading/error state and talks to the API; MenuList just draws what it's given. The hall
// comes from App's shared picker.

import { useEffect, useState } from 'react'
import { getMenu } from '../api.js'
import { useMealLogger } from '../useMealLogger.js'
import LogBanner from './LogBanner.jsx'
import MenuList from './MenuList.jsx'
import { RowsSkeleton } from './Skeleton.jsx'

/**
 * Loads today's menu for one hall and logs dishes from it.
 *
 * App gives this a `key` of the hall ID, so switching halls starts a fresh MenuView
 * (empty menu, "Loading…", no old banner) instead of resetting each piece of state by hand.
 *
 * @param {{hallId: string, onLogged?: () => void}} props - onLogged: called after each
 *   successful log, so App can tell the dashboard to reload.
 * @returns {JSX.Element}
 * @example <MenuView key={hallId} hallId="yahentamitsi" onLogged={() => setLogCount((c) => c + 1)} />
 */
export default function MenuView({ hallId, onLogged }) {
  const [menu, setMenu] = useState(null)
  const [error, setError] = useState(null)
  const { loggingId, logResult, handleLog } = useMealLogger(onLogged)

  useEffect(() => {
    // If this screen goes away (e.g. the hall changed) before the menu arrives, ignore the
    // late answer instead of updating a screen that's no longer shown.
    let stale = false
    getMenu(hallId)
      .then((loadedMenu) => !stale && setMenu(loadedMenu))
      .catch((err) => !stale && setError(err.message))
    return () => {
      stale = true
    }
  }, [hallId])

  return (
    <section className="menu-view card">
      <h2 className="card-title">Today's menu</h2>
      {error && <p className="notice notice--error">{error}</p>}
      {!error && !menu && (
        <div aria-busy="true">
          <p className="visually-hidden">Loading menu…</p>
          <RowsSkeleton count={6} />
        </div>
      )}
      <LogBanner result={logResult} />
      {menu && <MenuList items={menu.items} loggingId={loggingId} onLog={handleLog} />}
    </section>
  )
}
