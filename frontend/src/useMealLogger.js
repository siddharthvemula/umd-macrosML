// A custom React hook for logging a dish from the portion buttons. Both the menu screen and
// the photo screen use it, so "log it, then show a toast" lives in one place.

import { useEffect, useRef, useState } from 'react'
import { logMeal } from './api.js'

// How long the "Logged ..." toast stays up. Errors stay until the next log, since they need reading.
export const TOAST_MS = 3000

/**
 * Logs dishes and keeps the state the portion buttons and the result banner need.
 *
 * @param {() => void} [onLogged] - Called after each successful log, so App can reload the dashboard.
 * @param {number|null} [photoId] - The photo screen passes the current photo's id, so each
 *   log is linked to it as training data. The menu screen leaves it out.
 * @returns {{loggingId: string|null, logResult: {ok: boolean, text: string, id: number}|null,
 *   handleLog: (item: {recipe_id: string, name: string, suggested_servings?: number},
 *     servings: number) => Promise<void>}}
 *   loggingId: recipe_id being logged right now (its buttons are disabled), or null.
 *   logResult: the last log's message, or null. A success clears itself after TOAST_MS.
 *   id is new for every log, so the toast restarts its animation when you log twice in a row.
 * @example
 *   const { loggingId, logResult, handleLog } = useMealLogger(onLogged)
 *   handleLog(banana, 2)  // banner: "Logged 2x Banana (220 cal)."
 */
export function useMealLogger(onLogged, photoId = null) {
  const [loggingId, setLoggingId] = useState(null)
  const [logResult, setLogResult] = useState(null)
  // useRef keeps the timer between renders without causing a re-render when it changes.
  const hideTimer = useRef(null)
  const nextId = useRef(1)

  // If the screen goes away (e.g. hall switched) while a toast is up, cancel its timer.
  useEffect(() => () => clearTimeout(hideTimer.current), [])

  /**
   * Shows a result, replacing (and un-scheduling) the previous one.
   *
   * @param {boolean} ok
   * @param {string} text
   */
  function showResult(ok, text) {
    clearTimeout(hideTimer.current)
    setLogResult({ ok, text, id: nextId.current++ })
    if (ok) hideTimer.current = setTimeout(() => setLogResult(null), TOAST_MS)
  }

  async function handleLog(item, servings) {
    setLoggingId(item.recipe_id)
    try {
      // Photo guesses carry CLIP's suggested_servings; menu and search dishes don't (undefined).
      const log = await logMeal(item.recipe_id, servings, photoId, item.suggested_servings)
      // Use the server's calories (already multiplied by servings): it's what was saved.
      showResult(true, `Logged ${servings}x ${item.name} (${Math.round(log.calories)} cal).`)
      onLogged?.()
    } catch (err) {
      showResult(false, `Couldn't log ${item.name}: ${err.message}`)
    } finally {
      setLoggingId(null)
    }
  }

  return { loggingId, logResult, handleLog }
}
