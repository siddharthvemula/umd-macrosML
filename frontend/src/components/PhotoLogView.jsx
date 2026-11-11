// The "log from a photo" screen: one big "Snap a plate photo" button, then the photo next to
// the recognizer's top guesses from that day's menu (as cards), logged with portion buttons.
// A date picker (default today) lets a student upload a plate from a past day: the guesses
// come from that day's menu (the server scrapes it if missing) and the meal is logged on that day.
// A dish the recognizer missed can be found with "not listed? search the menu".
// Every log here carries the photo's id, so it becomes a training label.
// Photos are saved, so the camera only appears after the privacy notice is accepted.
// It owns the state and talks to the API; GuessList and MenuSearch just draw.

import { useEffect, useState } from 'react'
import { getMenu, recognizePhoto } from '../api.js'
import { todayOnCampus } from '../dates.js'
import { acceptPhotoNotice, hasAcceptedPhotoNotice } from '../privacy.js'
import { useMealLogger } from '../useMealLogger.js'
import GuessList from './GuessList.jsx'
import LogBanner from './LogBanner.jsx'
import MenuSearch from './MenuSearch.jsx'
import { PhotoNotice } from './PrivacyNotice.jsx'
import { RowsSkeleton } from './Skeleton.jsx'

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
  // Read once when the screen appears (a function, so localStorage isn't read on every render).
  const [noticeAccepted, setNoticeAccepted] = useState(hasAcceptedPhotoNotice)
  const [meal, setMeal] = useState('')
  // The day the plate was eaten ("YYYY-MM-DD"). Starts as today; max stops future days.
  // Read once; if the page stays open past midnight, the server's own "today" still rules.
  const [today] = useState(todayOnCampus)
  const [plateDate, setPlateDate] = useState(today)
  const [photo, setPhoto] = useState(null)
  // A temporary blob: URL so <img> can show the photo before (and without) uploading it.
  const [previewUrl, setPreviewUrl] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [guesses, setGuesses] = useState(null)
  // The server's id for the analyzed photo; every dish logged from it is linked to it.
  const [photoId, setPhotoId] = useState(null)
  const [error, setError] = useState(null)
  // Today's menu for the correction search: null until the student first opens it, then
  // kept (same hall and day) so later photos don't reload it.
  const [menuItems, setMenuItems] = useState(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [menuError, setMenuError] = useState(null)
  // undefined for today: the server then uses its own clock, as before this picker existed.
  const dateParam = plateDate === today ? undefined : plateDate
  const { loggingId, logResult, handleLog } = useMealLogger(onLogged, photoId, dateParam)
  const dayLabel = dateParam ? 'that day\'s menu' : 'today\'s menu'

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
   * @param {string|undefined} dateValue - "YYYY-MM-DD" of a past day, or undefined for today.
   */
  async function analyze(photoFile, mealName, dateValue) {
    setAnalyzing(true)
    setError(null)
    setGuesses(null)
    setPhotoId(null)
    try {
      const result = await recognizePhoto(photoFile, hallId, mealName, dateValue)
      setGuesses(result.guesses)
      setPhotoId(result.photo_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  /**
   * Opens the "search the menu" box, loading the day's menu the first time.
   */
  async function openSearch() {
    setSearchOpen(true)
    if (menuItems) return
    setMenuError(null)
    try {
      const menu = await getMenu(hallId, dateParam)
      setMenuItems(menu.items)
    } catch (err) {
      setMenuError(err.message)
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
    analyze(file, meal, dateParam)
  }

  /**
   * Changes the meal, and re-analyzes the current photo against that meal's dishes.
   *
   * @param {string} newMeal - e.g. "Dinner", or "".
   */
  function selectMeal(newMeal) {
    setMeal(newMeal)
    if (photo) analyze(photo, newMeal, dateParam)
  }

  /**
   * Changes the day the plate was eaten, and re-analyzes the current photo against that day's menu.
   *
   * @param {string} newDate - "YYYY-MM-DD", or "" if the user cleared the field (treated as today).
   */
  function selectDate(newDate) {
    // A typed or pasted future date can get past the input's max in some browsers.
    const chosen = newDate && newDate <= today ? newDate : today
    setPlateDate(chosen)
    // The cached menu and the open search belong to the old day.
    setMenuItems(null)
    setSearchOpen(false)
    if (photo) analyze(photo, meal, chosen === today ? undefined : chosen)
  }

  /**
   * Remembers the student accepted the notice and shows the camera input.
   */
  function handleAcceptNotice() {
    acceptPhotoNotice()
    setNoticeAccepted(true)
  }

  if (!noticeAccepted) {
    return (
      <section className="photo-log card">
        <h2 className="card-title">Log from a photo</h2>
        <PhotoNotice onAccept={handleAcceptNotice} />
      </section>
    )
  }

  /**
   * The file input, inside a label styled as a button. The real input is visually hidden
   * (but still focusable and read by screen readers), because browsers don't let us style
   * their own "Choose File" button well. Tapping the label opens the camera or file picker.
   *
   * @param {string} className - "photo-upload" (the big first button) or "button photo-retake".
   * @param {JSX.Element} children - The label's visible content, which is also its name.
   * @returns {JSX.Element}
   */
  function photoInput(className, children) {
    return (
      <label className={analyzing ? `${className} is-disabled` : className}>
        {children}
        {/* capture="environment" opens the back camera on phones; desktops show a file picker. */}
        <input
          className="visually-hidden"
          type="file"
          accept="image/*"
          capture="environment"
          disabled={analyzing}
          onChange={(event) => selectPhoto(event.target.files[0])}
        />
      </label>
    )
  }

  return (
    <section className="photo-log card">
      <div className="card-header">
        <h2 className="card-title">Log from a photo</h2>
        {/* All inputs are disabled while analyzing, so two requests can't race each other. */}
        <div className="photo-pickers">
          <label className="meal-picker">
            Day{' '}
            <input
              type="date"
              value={plateDate}
              max={today}
              disabled={analyzing}
              onChange={(event) => selectDate(event.target.value)}
            />
          </label>
          <label className="meal-picker">
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
        </div>
      </div>

      {/* Before a photo: one big button, the obvious first step on this screen. */}
      {!previewUrl && (
        <>
          {photoInput(
            'photo-upload',
            <>
              <span className="photo-upload-icon" aria-hidden="true">📷</span>
              <span className="photo-upload-title">Snap a plate photo</span>
            </>,
          )}
          <p className="photo-upload-hint">We'll match it against {dayLabel} at this hall.</p>
        </>
      )}

      {/* After a photo: the photo on the left (top on phones), the guesses beside it. */}
      {previewUrl && (
        <div className="photo-results">
          <div className="photo-side">
            <div className="photo-frame">
              <img className="photo-preview" src={previewUrl} alt="Your plate" />
              {analyzing && (
                <div className="photo-overlay">
                  <span className="spinner" aria-hidden="true" />
                  <span>Analyzing photo…</span>
                </div>
              )}
            </div>
            {photoInput('button photo-retake', <>Retake plate photo</>)}
          </div>

          <div className="photo-guesses">
            {analyzing && (
              <div aria-busy="true">
                <p className="notice">
                  The first photo can take about 10 seconds while the model loads.
                  {dateParam && " A day we haven't saved yet is fetched from UMD first, which can take longer."}
                </p>
                <RowsSkeleton count={3} />
              </div>
            )}
            {error && <p className="notice notice--error">{error}</p>}
            <LogBanner result={logResult} />
            {guesses && <GuessList guesses={guesses} loggingId={loggingId} onLog={handleLog} />}

            {/* Only with a saved photo: a correction is only useful linked to the photo it fixes. */}
            {guesses && photoId != null && !searchOpen && (
              <button type="button" className="button not-listed" onClick={openSearch}>
                Not listed? Search {dayLabel}
              </button>
            )}
            {guesses && photoId != null && searchOpen && (
              <>
                {menuError && <p className="notice notice--error">{menuError}</p>}
                {!menuItems && !menuError && <p className="notice">Loading {dayLabel}…</p>}
                {menuItems && (
                  <MenuSearch
                    items={menuItems}
                    meal={meal}
                    excludeIds={guesses.map((guess) => guess.recipe_id)}
                    loggingId={loggingId}
                    onLog={handleLog}
                    dayLabel={dayLabel}
                  />
                )}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
