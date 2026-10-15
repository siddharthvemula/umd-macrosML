// Tests for the photo screen (PhotoLogView + GuessList). api.js is faked, so no backend or
// CLIP model runs; we control what "the recognizer" answers and check what we sent it.

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getMenu, logMeal, recognizePhoto } from '../api.js'
import PhotoLogView from './PhotoLogView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()), // keep the real ApiError class
  recognizePhoto: vi.fn(),
  logMeal: vi.fn(),
  getMenu: vi.fn(),
}))

const PLATE = new File(['fake pixels'], 'plate.jpg', { type: 'image/jpeg' })

const TACOS = {
  recipe_id: '111*1', name: 'Beef Tacos', score: 0.31,
  nutrition: { calories: 250.4, protein_g: 14, carbs_g: 20, fat_g: 12 },
}
const SALSA = {
  recipe_id: '222*1', name: 'Pico de Gallo', score: 0.004,
  nutrition: { calories: 10, protein_g: 0, carbs_g: 2, fat_g: 0 },
}

const resultOf = (guesses, photoId = 7) => ({
  hall: 'yahentamitsi', date: '2026-10-15', meal: null, photo_id: photoId, guesses,
})

/**
 * Renders the photo screen for Yahentamitsi and picks the plate photo.
 *
 * @param {object} [props] - Extra props, e.g. { onLogged }.
 */
async function renderAndUpload(props = {}) {
  render(<PhotoLogView hallId="yahentamitsi" {...props} />)
  await userEvent.upload(screen.getByLabelText('Plate photo'), PLATE)
}

describe('PhotoLogView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    // jsdom has no blob: URLs, so fake the two functions the preview uses.
    URL.createObjectURL = vi.fn(() => 'blob:fake-preview')
    URL.revokeObjectURL = vi.fn()
  })

  it('uploads the chosen photo and shows the ranked guesses with their scores', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    await renderAndUpload()

    expect(await screen.findByText('Beef Tacos')).toBeInTheDocument()
    expect(recognizePhoto).toHaveBeenCalledWith(PLATE, 'yahentamitsi', '')
    expect(screen.getByText('31% match')).toBeInTheDocument()
    expect(screen.getByText('<1% match')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Your plate' })).toHaveAttribute('src', 'blob:fake-preview')
  })

  it('re-analyzes the same photo when the meal changes', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS]))
    await renderAndUpload()
    await screen.findByText('Beef Tacos')

    await userEvent.selectOptions(screen.getByLabelText('Meal'), 'Lunch')

    expect(recognizePhoto).toHaveBeenLastCalledWith(PLATE, 'yahentamitsi', 'Lunch')
  })

  it('logs a guess with the chosen portion and tells App', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    logMeal.mockResolvedValue({ id: 1, calories: 375.6 })
    const onLogged = vi.fn()
    await renderAndUpload({ onLogged })

    const tacoButtons = await screen.findByRole('group', { name: 'Log Beef Tacos' })
    await userEvent.click(within(tacoButtons).getByRole('button', { name: '1.5x' }))

    // 7 is the photo_id from the recognize result: this log becomes a training label.
    expect(logMeal).toHaveBeenCalledWith('111*1', 1.5, 7)
    expect(await screen.findByText('Logged 1.5x Beef Tacos (376 cal).')).toBeInTheDocument()
    expect(onLogged).toHaveBeenCalledTimes(1)
  })

  it("links logs to the newest photo's id after a re-analyze", async () => {
    recognizePhoto.mockResolvedValueOnce(resultOf([TACOS], 7)).mockResolvedValueOnce(resultOf([TACOS], 8))
    logMeal.mockResolvedValue({ id: 1, calories: 250 })
    await renderAndUpload()
    await screen.findByText('Beef Tacos')

    await userEvent.selectOptions(screen.getByLabelText('Meal'), 'Lunch')
    const tacoButtons = await screen.findByRole('group', { name: 'Log Beef Tacos' })
    await userEvent.click(within(tacoButtons).getByRole('button', { name: '1x' }))

    expect(logMeal).toHaveBeenCalledWith('111*1', 1, 8)
  })

  it('logs a dish the recognizer missed from the menu search, linked to the photo', async () => {
    const rice = { ...TACOS, recipe_id: '333*1', name: 'Spanish Rice', meal: 'Lunch', station: 'Grill' }
    recognizePhoto.mockResolvedValue(resultOf([TACOS], 7))
    getMenu.mockResolvedValue({ items: [{ ...TACOS, meal: 'Lunch', station: 'Grill' }, rice] })
    logMeal.mockResolvedValue({ id: 2, calories: 250 })
    await renderAndUpload()

    await userEvent.click(await screen.findByRole('button', { name: "Not listed? Search today's menu" }))
    await userEvent.type(await screen.findByLabelText("Search today's menu"), 'rice')
    const riceButtons = screen.getByRole('group', { name: 'Log Spanish Rice' })
    await userEvent.click(within(riceButtons).getByRole('button', { name: '1x' }))

    expect(getMenu).toHaveBeenCalledWith('yahentamitsi')
    expect(logMeal).toHaveBeenCalledWith('333*1', 1, 7)
  })

  it('does not list a dish twice when it is already a guess', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS], 7))
    getMenu.mockResolvedValue({ items: [{ ...TACOS, meal: 'Lunch', station: 'Grill' }] })
    await renderAndUpload()

    await userEvent.click(await screen.findByRole('button', { name: "Not listed? Search today's menu" }))
    await userEvent.type(await screen.findByLabelText("Search today's menu"), 'tacos')

    expect(screen.getByText('No dishes match "tacos".')).toBeInTheDocument()
  })

  it('offers no menu search when there was no photo to correct', async () => {
    recognizePhoto.mockResolvedValue(resultOf([], null))
    await renderAndUpload()
    await screen.findByText("No dishes with nutrition info on today's menu for this meal.")

    expect(screen.queryByRole('button', { name: /Not listed/ })).not.toBeInTheDocument()
  })

  it("shows the server's message when the photo can't be read", async () => {
    recognizePhoto.mockRejectedValue(new ApiError('That file is not a readable image.', 400))
    await renderAndUpload()

    expect(await screen.findByText('That file is not a readable image.')).toBeInTheDocument()
  })

  it('says so when there are no dishes to guess from', async () => {
    recognizePhoto.mockResolvedValue(resultOf([]))
    await renderAndUpload()

    expect(
      await screen.findByText("No dishes with nutrition info on today's menu for this meal."),
    ).toBeInTheDocument()
  })

  it('disables the inputs while a photo is being analyzed', async () => {
    // A promise we resolve by hand, to freeze the request "in flight".
    let finishRequest
    recognizePhoto.mockReturnValue(new Promise((resolve) => (finishRequest = resolve)))
    await renderAndUpload()

    expect(screen.getByText(/Analyzing photo/)).toBeInTheDocument()
    expect(screen.getByLabelText('Plate photo')).toBeDisabled()
    expect(screen.getByLabelText('Meal')).toBeDisabled()

    finishRequest(resultOf([TACOS]))
    await screen.findByText('Beef Tacos')
    expect(screen.getByLabelText('Plate photo')).toBeEnabled()
  })
})
