// The app's root component: the page header, today's dashboard, the shared hall picker,
// and the photo and menu screens. It connects them: when either screen logs a dish, the
// dashboard reloads, and both screens follow the one hall picker. The footer holds the
// privacy notice, so it's always one tap away.

import { useEffect, useState } from 'react'
import { getHalls } from './api.js'
import DashboardView from './components/DashboardView.jsx'
import HallPicker from './components/HallPicker.jsx'
import MenuView from './components/MenuView.jsx'
import PhotoLogView from './components/PhotoLogView.jsx'
import { PrivacyDetails } from './components/PrivacyNotice.jsx'

/**
 * Top-level layout of the page.
 *
 * @returns {JSX.Element}
 */
export default function App() {
  // Goes up by 1 after every successful log. The dashboard reloads when it changes, so the
  // screens stay in sync without sharing all their data.
  const [logCount, setLogCount] = useState(0)
  const [halls, setHalls] = useState([])
  const [hallId, setHallId] = useState(null)
  const [hallsError, setHallsError] = useState(null)

  // Load the hall list once, when the page first appears, and pick the first hall.
  useEffect(() => {
    getHalls()
      .then((loadedHalls) => {
        setHalls(loadedHalls)
        setHallId(loadedHalls[0]?.id ?? null)
      })
      .catch((err) => setHallsError(err.message))
  }, [])

  const handleLogged = () => setLogCount((count) => count + 1)

  return (
    <main className="app">
      <h1>UMD Dining Macros</h1>
      <DashboardView refreshKey={logCount} />

      {hallsError && <p className="notice notice--error">{hallsError}</p>}
      {!hallsError && !hallId && <p className="notice">Loading halls…</p>}
      {hallId && (
        <>
          <HallPicker halls={halls} hallId={hallId} onChange={setHallId} />
          {/* A new key makes React start these screens fresh when the hall changes, so no
              menu, photo or guesses from the old hall are left over. */}
          <PhotoLogView key={`photo-${hallId}`} hallId={hallId} onLogged={handleLogged} />
          <MenuView key={`menu-${hallId}`} hallId={hallId} onLogged={handleLogged} />
        </>
      )}

      <footer className="app-footer">
        {/* <details> is a built-in show/hide box: no state or JavaScript needed. */}
        <details>
          <summary>Privacy</summary>
          <PrivacyDetails />
        </details>
      </footer>
    </main>
  )
}
