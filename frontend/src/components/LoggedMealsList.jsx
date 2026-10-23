// The list of dishes logged today, each with a Delete button. Display only: it gets the
// logs and an onDelete callback as props and never calls the API itself.

/**
 * Today's logged dishes, oldest first.
 *
 * @param {{meals: object[], deletingId: number|null, onDelete: (meal: object) => void}} props
 *   meals: logs from getMeals(). deletingId: id of the log being deleted right now (its button
 *   is disabled). onDelete: called when a Delete button is clicked.
 * @returns {JSX.Element}
 * @example <LoggedMealsList meals={[bananaLog]} deletingId={null} onDelete={handleDelete} />
 *   // one row: "Banana · 2x · 220 cal [Delete]"
 */
export default function LoggedMealsList({ meals, deletingId, onDelete }) {
  if (meals.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">🍽️</span>
        <p className="empty-state-title">Nothing logged yet today.</p>
        <p className="empty-state-hint">Snap a photo of your plate, or log a dish from today's menu.</p>
      </div>
    )
  }

  return (
    <ul className="logged-meals">
      {meals.map((meal) => (
        <li key={meal.id} className="logged-meal">
          <span className="dish-name">{meal.name}</span>
          <span className="dish-macros">
            {`${meal.servings}x · ${Math.round(meal.calories)} cal`}
          </span>
          <button
            type="button"
            aria-label={`Delete ${meal.name}`}
            disabled={meal.id === deletingId}
            onClick={() => onDelete(meal)}
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  )
}
