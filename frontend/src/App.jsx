// The app's root component: the page header and the menu screen.

import MenuView from './components/MenuView.jsx'

/**
 * Top-level layout of the page.
 *
 * @returns {JSX.Element}
 */
export default function App() {
  return (
    <main className="app">
      <h1>UMD Dining Macros</h1>
      <MenuView />
    </main>
  )
}
