// The recognizer's top guesses for a plate photo, as cards: rank, name, a "% match" badge and
// bar, the macros, and portion buttons. Display only:
// it gets the guesses and an onLog callback and never calls the API itself.

import PortionButtons from './PortionButtons.jsx'

/**
 * Ranked dish guesses, best first. A plate usually has several dishes, so any number of
 * them can be logged.
 *
 * @param {{guesses: object[], loggingId: string|null, onLog: (guess: object, servings: number) => void}} props
 *   guesses: from recognizePhoto(), each with recipe_id, name, score and nutrition.
 * @returns {JSX.Element}
 * @example <GuessList guesses={result.guesses} loggingId={null} onLog={handleLog} />
 */
export default function GuessList({ guesses, loggingId, onLog }) {
  if (guesses.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">🤷</span>
        <p className="empty-state-title">No dishes with nutrition info on today's menu for this meal.</p>
        <p className="empty-state-hint">Try another meal above, or log from the menu below.</p>
      </div>
    )
  }

  return (
    <>
      <p className="guess-intro">Tap a portion for each dish on your plate.</p>
      <ol className="guess-list">
        {guesses.map((guess, index) => {
          const { nutrition } = guess
          return (
            <li key={guess.recipe_id} className="guess-card">
              <div className="guess-top">
                <span className="guess-rank" aria-hidden="true">{index + 1}</span>
                <span className="dish-name">{guess.name}</span>
                <span className="match-badge">{formatScore(guess.score)} match</span>
              </div>
              {/* The bar shows the real score, not one scaled to the top guess, so a weak
                  "best" guess also looks weak. At least 2% wide, so a tiny score is still visible. */}
              <div className="match-bar" aria-hidden="true">
                <span style={{ width: `${Math.max(guess.score * 100, 2)}%` }} />
              </div>
              <span className="dish-meta">
                {`${Math.round(nutrition.calories)} cal · ${nutrition.protein_g}g protein · ` +
                  `${nutrition.carbs_g}g carbs · ${nutrition.fat_g}g fat per serving`}
              </span>
              <PortionButtons
                dishName={guess.name}
                disabled={guess.recipe_id === loggingId}
                onLog={(servings) => onLog(guess, servings)}
              />
            </li>
          )
        })}
      </ol>
    </>
  )
}

/**
 * Turns a 0-1 score into a percentage label.
 *
 * Scores are spread over ~200 candidate dishes, so even a correct guess can be a few
 * percent; "<1%" reads better than "0%".
 *
 * @param {number} score - e.g. 0.123
 * @returns {string} e.g. "12%"
 */
function formatScore(score) {
  const percent = Math.round(score * 100)
  return percent < 1 ? '<1%' : `${percent}%`
}
