// The app's root component: the page header, today's dashboard, and the menu screen.
// It also connects the two screens: when the menu logs a dish, the dashboard reloads.

import { useState } from 'react'
import DashboardView from './components/DashboardView.jsx'
import MenuView from './components/MenuView.jsx'

/**
 * Top-level layout of the page.
 *
 * @returns {JSX.Element}
 */
export default function App() {
  // Goes up by 1 after every successful log. The dashboard reloads when it changes, so the
  // two screens stay in sync without sharing all their data.
  const [logCount, setLogCount] = useState(0)

  return (
    <main className="app">
      <h1>UMD Dining Macros</h1>
      <DashboardView refreshKey={logCount} />
      <MenuView onLogged={() => setLogCount((count) => count + 1)} />
    </main>
  )
}
