// A custom React hook for logging a dish from the portion buttons. Both the menu screen and
// the photo screen use it, so "log it, then show a banner" lives in one place.

import { useState } from 'react'
import { logMeal } from './api.js'

/**
 * Logs dishes and keeps the state the portion buttons and the result banner need.
 *
 * @param {() => void} [onLogged] - Called after each successful log, so App can reload the dashboard.
 * @param {number|null} [photoId] - The photo screen passes the current photo's id, so each
 *   log is linked to it as training data. The menu screen leaves it out.
 * @returns {{loggingId: string|null, logResult: {ok: boolean, text: string}|null,
 *   handleLog: (item: {recipe_id: string, name: string}, servings: number) => Promise<void>}}
 *   loggingId: recipe_id being logged right now (its buttons are disabled), or null.
 *   logResult: the last log's banner, or null.
 * @example
 *   const { loggingId, logResult, handleLog } = useMealLogger(onLogged)
 *   handleLog(banana, 2)  // banner: "Logged 2x Banana (220 cal)."
 */
export function useMealLogger(onLogged, photoId = null) {
  const [loggingId, setLoggingId] = useState(null)
  const [logResult, setLogResult] = useState(null)

  async function handleLog(item, servings) {
    setLoggingId(item.recipe_id)
    try {
      const log = await logMeal(item.recipe_id, servings, photoId)
      // Use the server's calories (already multiplied by servings): it's what was saved.
      setLogResult({ ok: true, text: `Logged ${servings}x ${item.name} (${Math.round(log.calories)} cal).` })
      onLogged?.()
    } catch (err) {
      setLogResult({ ok: false, text: `Couldn't log ${item.name}: ${err.message}` })
    } finally {
      setLoggingId(null)
    }
  }

  return { loggingId, logResult, handleLog }
}
