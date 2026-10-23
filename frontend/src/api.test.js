// Tests for api.js. fetch is replaced with a fake (vi.fn), so these check which URLs and
// bodies we send and how we handle answers, without a running backend.

import { describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  deleteMeal,
  getHalls,
  getMenu,
  getSummary,
  logMeal,
  recognizePhoto,
} from './api.js'

/**
 * Replaces the global fetch with a fake that always returns one response.
 *
 * @param {number} status - HTTP status code to answer with.
 * @param {any} [body] - JSON body; leave out for an empty response.
 * @returns {import('vitest').Mock} The fake, so tests can check how it was called.
 */
function fakeFetch(status, body) {
  // A new Response per call: a response body can only be read once.
  const fetchMock = vi.fn(async () =>
    new Response(body === undefined ? null : JSON.stringify(body), { status }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('api', () => {
  it('getHalls requests /api/halls and returns the JSON', async () => {
    const fetchMock = fakeFetch(200, [{ id: 'south_campus', name: 'South Campus' }])

    expect(await getHalls()).toEqual([{ id: 'south_campus', name: 'South Campus' }])
    expect(fetchMock.mock.calls[0][0]).toBe('/api/halls')
  })

  it('sends the same device ID header with every request', async () => {
    const fetchMock = fakeFetch(200, [])

    await getHalls()
    await logMeal('111*1', 1)

    const [first, second] = fetchMock.mock.calls.map(([, options]) => options.headers['X-Device-Id'])
    expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(second).toBe(first)
    // Adding the device header must not drop logMeal's own JSON header.
    expect(fetchMock.mock.calls[1][1].headers['Content-Type']).toBe('application/json')
  })

  it('getMenu adds the date only when one is given', async () => {
    const fetchMock = fakeFetch(200, { items: [] })

    await getMenu('yahentamitsi')
    await getMenu('yahentamitsi', '2026-10-12')

    expect(fetchMock.mock.calls[0][0]).toBe('/api/menu?hall=yahentamitsi')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/menu?hall=yahentamitsi&date=2026-10-12')
  })

  it('logMeal POSTs the recipe and servings as JSON', async () => {
    const fetchMock = fakeFetch(201, { id: 1, servings: 1.5 })

    await logMeal('111*1', 1.5)

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/meals')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ recipe_id: '111*1', servings: 1.5 })
  })

  it('logMeal adds photo_id only when a photo is given', async () => {
    const fetchMock = fakeFetch(201, { id: 1 })

    await logMeal('111*1', 1, 7)
    await logMeal('111*1', 1, null)

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ recipe_id: '111*1', servings: 1, photo_id: 7 })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ recipe_id: '111*1', servings: 1 })
  })

  it('logMeal adds suggested_servings only with a photo', async () => {
    const fetchMock = fakeFetch(201, { id: 1 })

    await logMeal('111*1', 1.25, 7, 1.5)
    await logMeal('111*1', 1, null, 1.5)

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(
      { recipe_id: '111*1', servings: 1.25, photo_id: 7, suggested_servings: 1.5 },
    )
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ recipe_id: '111*1', servings: 1 })
  })

  it('recognizePhoto POSTs the photo, hall and meal as form data', async () => {
    const fetchMock = fakeFetch(200, { guesses: [] })
    const photo = new File(['fake pixels'], 'plate.jpg', { type: 'image/jpeg' })

    await recognizePhoto(photo, 'yahentamitsi', 'Lunch')

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/recognize')
    expect(options.method).toBe('POST')
    // No Content-Type: the browser must write the multipart one (with its boundary) itself.
    expect(options.headers['Content-Type']).toBeUndefined()
    expect(options.body.get('photo').name).toBe('plate.jpg')
    expect(options.body.get('hall')).toBe('yahentamitsi')
    expect(options.body.get('meal')).toBe('Lunch')
  })

  it('recognizePhoto leaves out an empty meal', async () => {
    const fetchMock = fakeFetch(200, { guesses: [] })

    await recognizePhoto(new File(['x'], 'plate.jpg'), 'yahentamitsi', '')

    expect(fetchMock.mock.calls[0][1].body.has('meal')).toBe(false)
  })

  it('recognizePhoto turns a 400 for a non-image into an ApiError', async () => {
    fakeFetch(400, { detail: 'That file is not a readable image.' })

    const error = await recognizePhoto(new File(['x'], 'notes.txt'), 'yahentamitsi').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(400)
    expect(error.message).toBe('That file is not a readable image.')
  })

  it('deleteMeal returns null for the empty 204 response', async () => {
    fakeFetch(204)
    expect(await deleteMeal(7)).toBeNull()
  })

  it("passes on FastAPI's error detail with the status", async () => {
    fakeFetch(404, { detail: "No nutrition stored for recipe '999*1'." })

    const error = await logMeal('999*1', 1).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe("No nutrition stored for recipe '999*1'.")
  })

  it('uses a generic message when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 })))

    await expect(getSummary()).rejects.toThrow('Request failed (HTTP 502).')
  })

  it('explains that the server is unreachable when fetch itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await getHalls().catch((e) => e)

    expect(error.status).toBeNull()
    expect(error.message).toMatch(/Can't reach the server/)
  })
})
