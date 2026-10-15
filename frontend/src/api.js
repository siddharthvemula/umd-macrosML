// The only file that talks to the FastAPI backend. Components call these functions
// instead of building URLs themselves, so tests can fake the API in one place and a
// backend change only needs updating here. Every URL starts with /api, which Vite's dev
// server proxies to FastAPI (see vite.config.js).

const API_BASE = '/api'

/** Thrown when the backend can't be reached or answers with an error status. */
export class ApiError extends Error {
  /**
   * @param {string} message - Readable explanation to show the user.
   * @param {number|null} status - HTTP status code, or null if the request never got an answer.
   */
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Sends one request and returns the parsed JSON, turning every failure into an ApiError.
 *
 * @param {string} path - Path after /api, e.g. "/menu?hall=south_campus".
 * @param {RequestInit} [options] - fetch options (method, body, headers).
 * @returns {Promise<any>} The JSON body, or null for an empty response (204).
 * @example
 *   await request('/halls')  // -> [{ id: 'south_campus', name: 'South Campus' }]
 */
async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, options)
  } catch {
    // fetch only throws when there's no response at all, e.g. the backend isn't running.
    throw new ApiError("Can't reach the server. Is the backend running?", null)
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }
  return response.status === 204 ? null : response.json()
}

/**
 * Pulls FastAPI's error message out of a failed response.
 *
 * FastAPI sends {"detail": "..."} for our 404s, but a list of problems for 422 validation
 * errors, and the body may not be JSON at all (e.g. the proxy's 502), so fall back to the status.
 *
 * @param {Response} response - A response with a 4xx/5xx status.
 * @returns {Promise<string>} e.g. "No nutrition stored for recipe '111*1'."
 */
async function readErrorMessage(response) {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Not JSON: use the generic message below.
  }
  return `Request failed (HTTP ${response.status}).`
}

/**
 * Builds a query string, leaving out params that are undefined.
 *
 * @param {Record<string, string|undefined>} params
 * @returns {string} e.g. "?hall=south_campus" (or "" if nothing is set)
 */
function queryString(params) {
  const defined = Object.entries(params).filter(([, value]) => value !== undefined)
  return defined.length ? `?${new URLSearchParams(defined)}` : ''
}

/**
 * Lists the dining halls we have menus for.
 *
 * @returns {Promise<{id: string, name: string}[]>}
 * @example await getHalls()  // -> [{ id: 'south_campus', name: 'South Campus' }, ...]
 */
export function getHalls() {
  return request('/halls')
}

/**
 * Gets one hall's menu for a day (today if date is left out).
 *
 * @param {string} hall - Hall ID from getHalls(), e.g. "yahentamitsi".
 * @param {string} [date] - "YYYY-MM-DD".
 * @returns {Promise<{hall: string, date: string, items: object[]}>} Each item has name,
 *   recipe_id, station, meal and nutrition (null if we have no label).
 * @example await getMenu('south_campus')  // -> { hall: 'south_campus', date: '2026-10-13', items: [...] }
 */
export function getMenu(hall, date) {
  return request(`/menu${queryString({ hall, date })}`)
}

/**
 * Logs that the student ate some servings of a dish.
 *
 * @param {string} recipeId - e.g. "080603*4".
 * @param {number} servings - Between 0 (exclusive) and 5, e.g. 1.5.
 * @param {number|null} [photoId] - The plate photo this dish was picked from (from
 *   recognizePhoto()), which turns the log into an ML training label. Leave out for menu logs.
 * @returns {Promise<object>} The new log, with macros already multiplied by servings.
 * @example await logMeal('111*1', 2)  // -> { id: 1, name: 'Banana', servings: 2, calories: 219.6, ... }
 * @example await logMeal('111*1', 1, 7)  // same, plus photo_id: 7
 */
export function logMeal(recipeId, servings, photoId) {
  const body = { recipe_id: recipeId, servings }
  // Only send photo_id when there is one, so menu logs look exactly as before.
  if (photoId != null) body.photo_id = photoId
  return request('/meals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/**
 * Lists the dishes logged on a day (today if date is left out), oldest first.
 *
 * @param {string} [date] - "YYYY-MM-DD".
 * @returns {Promise<object[]>}
 */
export function getMeals(date) {
  return request(`/meals${queryString({ date })}`)
}

/**
 * Deletes one logged dish.
 *
 * @param {number} logId - The log's id from getMeals() or logMeal().
 * @returns {Promise<null>}
 */
export function deleteMeal(logId) {
  return request(`/meals/${logId}`, { method: 'DELETE' })
}

/**
 * Gets a day's macro totals (today if date is left out).
 *
 * @param {string} [date] - "YYYY-MM-DD".
 * @returns {Promise<{date: string, calories: number, protein_g: number, carbs_g: number,
 *   fat_g: number, meal_count: number}>}
 */
export function getSummary(date) {
  return request(`/summary${queryString({ date })}`)
}

/**
 * Uploads a plate photo and gets the recognizer's top guesses from today's menu.
 *
 * Sent as multipart form data (how browsers upload files), not JSON. We don't set
 * Content-Type ourselves: the browser has to add the multipart "boundary" to it.
 *
 * @param {File|Blob} photo - The image the user picked or took.
 * @param {string} hall - Hall ID, e.g. "yahentamitsi".
 * @param {string} [meal] - e.g. "Lunch"; leave out (or "") to consider the whole day's menu.
 * @returns {Promise<{hall: string, date: string, meal: string|null, photo_id: number|null,
 *   guesses: object[]}>} Each guess has recipe_id, name, score (0-1) and nutrition.
 *   photo_id is the saved photo (null if there were no guesses); pass it to logMeal().
 * @example await recognizePhoto(file, 'yahentamitsi', 'Lunch')  // -> { guesses: [{ name: 'Banana', score: 0.42, ... }] }
 */
export function recognizePhoto(photo, hall, meal) {
  const form = new FormData()
  form.append('photo', photo)
  form.append('hall', hall)
  if (meal) form.append('meal', meal)
  return request('/recognize', { method: 'POST', body: form })
}
