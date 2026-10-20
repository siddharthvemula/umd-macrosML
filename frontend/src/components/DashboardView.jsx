// The "Today" dashboard: the day's macro totals as rings that fill toward the daily goals,
// plus the dishes logged so far, with delete. It owns the loading/error state, the goals and
// the API calls; MacroTotals, GoalsForm and LoggedMealsList just draw what they're given.

import { useEffect, useState } from 'react'
import { deleteMeal, getMeals, getSummary } from '../api.js'
import { loadGoals, saveGoals } from '../goals.js'
import GoalsForm from './GoalsForm.jsx'
import LoggedMealsList from './LoggedMealsList.jsx'
import MacroTotals from './MacroTotals.jsx'
import { RingsSkeleton, RowsSkeleton } from './Skeleton.jsx'

/**
 * Loads today's totals and logs, and reloads them when refreshKey changes or a log is deleted.
 *
 * @param {{refreshKey: number}} props - refreshKey: a counter App bumps after each new log,
 *   so the dashboard knows to reload.
 * @returns {JSX.Element}
 * @example <DashboardView refreshKey={logCount} />
 */
export default function DashboardView({ refreshKey }) {
  // { summary, meals } once loaded, or null while the first load is running.
  const [day, setDay] = useState(null)
  const [error, setError] = useState(null)
  // id of the log being deleted right now (its button is disabled), or null.
  const [deletingId, setDeletingId] = useState(null)
  // Read once when the dashboard appears (a function, so localStorage isn't read every render).
  const [goals, setGoals] = useState(loadGoals)
  const [editingGoals, setEditingGoals] = useState(false)

  // Reload whenever App says something was logged. Same "stale" guard as MenuView: if two
  // reloads overlap, only the newest answer is shown.
  useEffect(() => {
    let stale = false
    loadDay()
      .then((loadedDay) => {
        if (stale) return
        setDay(loadedDay)
        setError(null)
      })
      .catch((err) => !stale && setError(err.message))
    return () => {
      stale = true
    }
  }, [refreshKey])

  /**
   * Deletes one log, then reloads the totals from the server.
   *
   * @param {{id: number, name: string}} meal - The log to delete.
   * @example handleDelete(bananaLog)  // Banana disappears and the totals drop
   */
  async function handleDelete(meal) {
    setDeletingId(meal.id)
    try {
      await deleteMeal(meal.id)
      // Reload rather than subtract in the browser, so the totals are always the server's.
      setDay(await loadDay())
      setError(null)
    } catch (err) {
      setError(`Couldn't delete ${meal.name}: ${err.message}`)
    } finally {
      setDeletingId(null)
    }
  }

  /**
   * Saves new goals and closes the form.
   *
   * @param {object} newGoals - From GoalsForm, already cleaned.
   */
  function handleSaveGoals(newGoals) {
    setGoals(saveGoals(newGoals))
    setEditingGoals(false)
  }

  return (
    <section className="dashboard card">
      <div className="card-header">
        <h2 className="card-title">Today</h2>
        {!editingGoals && (
          <button type="button" className="link-button" onClick={() => setEditingGoals(true)}>
            Edit goals
          </button>
        )}
      </div>
      {editingGoals && <GoalsForm goals={goals} onSave={handleSaveGoals} onCancel={() => setEditingGoals(false)} />}
      {error && <p className="notice notice--error">{error}</p>}
      {!error && !day && (
        <div aria-busy="true">
          {/* Screen readers hear this; everyone else sees the gray placeholders. */}
          <p className="visually-hidden">Loading today's totals…</p>
          <RingsSkeleton />
          <RowsSkeleton count={2} />
        </div>
      )}
      {day && (
        <>
          <MacroTotals summary={day.summary} goals={goals} />
          <LoggedMealsList meals={day.meals} deletingId={deletingId} onDelete={handleDelete} />
        </>
      )}
    </section>
  )
}

/**
 * Fetches today's summary and logs at the same time (one wait instead of two in a row).
 *
 * @returns {Promise<{summary: object, meals: object[]}>}
 * @example await loadDay()  // -> { summary: { calories: 219.6, ... }, meals: [bananaLog] }
 */
async function loadDay() {
  const [summary, meals] = await Promise.all([getSummary(), getMeals()])
  return { summary, meals }
}
