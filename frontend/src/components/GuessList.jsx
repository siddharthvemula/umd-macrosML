// The recognizer's top guesses for a plate photo, each with portion buttons. Display only:
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
    return <p className="notice">No dishes with nutrition info on today's menu for this meal.</p>
  }

  return (
    <>
      <p className="notice">Tap a portion for each dish on your plate.</p>
      <ol className="dish-list">
        {guesses.map((guess) => (
          <li key={guess.recipe_id} className="dish">
            <div>
              <span className="dish-name">{guess.name}</span>
              <span className="dish-station">{formatScore(guess.score)} match</span>
            </div>
            <div className="dish-macros">
              <span>{Math.round(guess.nutrition.calories)} cal per serving</span>
              <PortionButtons
                dishName={guess.name}
                disabled={guess.recipe_id === loggingId}
                onLog={(servings) => onLog(guess, servings)}
              />
            </div>
          </li>
        ))}
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
