// The "log from a photo" screen: pick a meal, take or choose a plate photo, see the
// recognizer's top guesses from today's menu, and log the right ones with portion buttons.
// It owns the state and talks to the API; GuessList just draws the guesses.

import { useEffect, useState } from 'react'
import { recognizePhoto } from '../api.js'
import { useMealLogger } from '../useMealLogger.js'
import GuessList from './GuessList.jsx'
import LogBanner from './LogBanner.jsx'

// "" means "any meal": the backend then picks from the whole day's menu.
const MEALS = ['Breakfast', 'Brunch', 'Lunch', 'Dinner']

/**
 * Uploads a plate photo for one hall and logs dishes from the guesses.
 *
 * Like MenuView, App gives this a `key` of the hall ID, so switching halls clears the
 * photo and guesses (they came from the other hall's menu).
 *
 * @param {{hallId: string, onLogged?: () => void}} props
 * @returns {JSX.Element}
 * @example <PhotoLogView key={hallId} hallId="yahentamitsi" onLogged={() => setLogCount((c) => c + 1)} />
 */
export default function PhotoLogView({ hallId, onLogged }) {
  const [meal, setMeal] = useState('')
  const [photo, setPhoto] = useState(null)
  // A temporary blob: URL so <img> can show the photo before (and without) uploading it.
  const [previewUrl, setPreviewUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [guesses, setGuesses] = useState(null)
  // The server's id for the analyzed photo; every dish logged from it is linked to it.
  const [photoId, setPhotoId] = useState(null)
  const [error, setError] = useState(null)
  const { loggingId, logResult, handleLog } = useMealLogger(onLogged, photoId)

  // Blob URLs hold the photo in memory until revoked. Free the old one when a new photo
  // replaces it, and the last one when the screen goes away.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  /**
   * Sends the photo to the recognizer and shows its guesses (or the error).
   *
   * @param {File} photoFile
   * @param {string} mealName - e.g. "Lunch", or "" for any meal.
   */
  async function analyze(photoFile, mealName) {
    setAnalyzing(true)
    setError(null)
    setGuesses(null)
    setPhotoId(null)
    try {
      const result = await recognizePhoto(photoFile, hallId, mealName)
      setGuesses(result.guesses)
      setPhotoId(result.photo_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  /**
   * Shows the chosen photo and analyzes it right away (no separate "Analyze" button).
   *
   * @param {File|undefined} file - undefined if the user closed the picker without choosing.
   */
  function selectPhoto(file) {
    if (!file) return
    setPhoto(file)
    setPreviewUrl(URL.createObjectURL(file))
    analyze(file, meal)
  }

  /**
   * Changes the meal, and re-analyzes the current photo against that meal's dishes.
   *
   * @param {string} newMeal - e.g. "Dinner", or "".
   */
  function selectMeal(newMeal) {
    setMeal(newMeal)
    if (photo) analyze(photo, newMeal)
  }

  return (
    <section className="photo-log">
      <h2>Log from a photo</h2>
      {/* Both inputs are disabled while analyzing, so two requests can't race each other. */}
      <div className="photo-controls">
        <label>
          Meal{' '}
          <select value={meal} disabled={analyzing} onChange={(event) => selectMeal(event.target.value)}>
            <option value="">Any</option>
            {MEALS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Plate photo{' '}
          {/* capture="environment" opens the back camera on phones; desktops show a file picker. */}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            disabled={analyzing}
            onChange={(event) => selectPhoto(event.target.files[0])}
          />
        </label>
      </div>

      {previewUrl && <img className="photo-preview" src={previewUrl} alt="Your plate" />}
      {analyzing && (
        <p className="notice">Analyzing photo… the first one can take about 10 seconds while the model loads.</p>
      )}
      {error && <p className="notice notice--error">{error}</p>}
      <LogBanner result={logResult} />
      {guesses && <GuessList guesses={guesses} loggingId={loggingId} onLog={handleLog} />}
    </section>
  )
}
