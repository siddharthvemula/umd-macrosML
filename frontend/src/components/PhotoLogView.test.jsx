// Tests for the photo screen (PhotoLogView + GuessList). api.js is faked, so no backend or
// CLIP model runs; we control what "the recognizer" answers and check what we sent it.

import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getMenu, logMeal, recognizePhoto } from '../api.js'
import { todayOnCampus } from '../dates.js'
import PhotoLogView from './PhotoLogView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()), // keep the real ApiError class
  recognizePhoto: vi.fn(),
  logMeal: vi.fn(),
  getMenu: vi.fn(),
}))

const PLATE = new File(['fake pixels'], 'plate.jpg', { type: 'image/jpeg' })

const TACOS = {
  recipe_id: '111*1', name: 'Beef Tacos', score: 0.31, suggested_servings: 1.5,
  nutrition: { calories: 250.4, protein_g: 14, carbs_g: 20, fat_g: 12 },
}
const SALSA = {
  recipe_id: '222*1', name: 'Pico de Gallo', score: 0.004, suggested_servings: 1,
  nutrition: { calories: 10, protein_g: 0, carbs_g: 2, fat_g: 0 },
}

// Tacos as getMenu() returns it: menu items have no suggested_servings, only guesses do.
const TACOS_ON_MENU = {
  recipe_id: '111*1', name: 'Beef Tacos', meal: 'Lunch', station: 'Grill', nutrition: TACOS.nutrition,
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
  await userEvent.upload(screen.getByLabelText(/plate photo/i), PLATE)
}

describe('PhotoLogView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    // jsdom has no blob: URLs, so fake the two functions the preview uses.
    URL.createObjectURL = vi.fn(() => 'blob:fake-preview')
    URL.revokeObjectURL = vi.fn()
    // Most tests are about uploading, so start past the privacy notice (tested below).
    window.localStorage.clear()
    window.localStorage.setItem('macros.photoNoticeAccepted', 'yes')
  })

  it('shows the privacy notice instead of the camera until it is accepted', async () => {
    window.localStorage.clear()
    render(<PhotoLogView hallId="yahentamitsi" />)

    expect(screen.getByRole('region', { name: 'Photo privacy notice' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Plate photo')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'I understand' }))
    expect(screen.getByLabelText(/plate photo/i)).toBeInTheDocument()
  })

  it('shows a short notice, with the full text only after "Read more"', async () => {
    window.localStorage.clear()
    render(<PhotoLogView hallId="yahentamitsi" />)

    expect(screen.getByText(/Plate photos are saved/)).toBeInTheDocument()
    expect(screen.queryByText(/Delete your data/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Read more' }))
    expect(screen.getByText(/Delete your data/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Show less' }))
    expect(screen.queryByText(/Delete your data/)).not.toBeInTheDocument()
  })

  it('remembers the accepted notice on later visits', async () => {
    window.localStorage.clear()
    const { unmount } = render(<PhotoLogView hallId="yahentamitsi" />)
    await userEvent.click(screen.getByRole('button', { name: 'I understand' }))
    unmount()

    render(<PhotoLogView hallId="yahentamitsi" />)
    expect(screen.getByLabelText(/plate photo/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'I understand' })).not.toBeInTheDocument()
  })

  it('uploads the chosen photo and shows the ranked guesses with their scores', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    await renderAndUpload()

    expect(await screen.findByText('Beef Tacos')).toBeInTheDocument()
    expect(recognizePhoto).toHaveBeenCalledWith(PLATE, 'yahentamitsi', '', undefined)
    expect(screen.getByText('31% match')).toBeInTheDocument()
    expect(screen.getByText('<1% match')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Your plate' })).toHaveAttribute('src', 'blob:fake-preview')
  })

  it('re-analyzes the same photo when the meal changes', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS]))
    await renderAndUpload()
    await screen.findByText('Beef Tacos')

    await userEvent.selectOptions(screen.getByLabelText('Meal'), 'Lunch')

    expect(recognizePhoto).toHaveBeenLastCalledWith(PLATE, 'yahentamitsi', 'Lunch', undefined)
  })

  it('logs a guess at its suggested portion and tells App', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    logMeal.mockResolvedValue({ id: 1, calories: 375.6 })
    const onLogged = vi.fn()
    await renderAndUpload({ onLogged })

    const tacoButtons = await screen.findByRole('group', { name: 'Log Beef Tacos' })
    await userEvent.click(within(tacoButtons).getByRole('button', { name: 'Log 1.5x' }))

    // 7 is the photo_id from the recognize result: this log becomes a training label.
    expect(logMeal).toHaveBeenCalledWith('111*1', 1.5, 7, 1.5, undefined)
    expect(await screen.findByText('Logged 1.5x Beef Tacos (376 cal).')).toBeInTheDocument()
    expect(onLogged).toHaveBeenCalledTimes(1)
  })

  it("starts each guess at CLIP's suggested portion, labeled, and can be changed", async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    logMeal.mockResolvedValue({ id: 1, calories: 250 })
    await renderAndUpload()

    const tacos = await screen.findByRole('group', { name: 'Log Beef Tacos' })
    expect(within(tacos).getByText('Suggested: 1.5x')).toBeInTheDocument()
    expect(within(tacos).getByText('1.5x')).toBeInTheDocument()
    expect(within(tacos).getByText('376 cal · 21g protein · 30g carbs · 18g fat')).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Log Pico de Gallo' })).getByText('Suggested: 1x')).toBeInTheDocument()

    await userEvent.click(within(tacos).getByRole('button', { name: 'Fewer servings' }))
    await userEvent.click(within(tacos).getByRole('button', { name: 'Log 1.25x' }))
    expect(logMeal).toHaveBeenCalledWith('111*1', 1.25, 7, 1.5, undefined)  // chosen 1.25, suggested 1.5
  })

  it("links logs to the newest photo's id after a re-analyze", async () => {
    recognizePhoto.mockResolvedValueOnce(resultOf([TACOS], 7)).mockResolvedValueOnce(resultOf([TACOS], 8))
    logMeal.mockResolvedValue({ id: 1, calories: 250 })
    await renderAndUpload()
    await screen.findByText('Beef Tacos')

    await userEvent.selectOptions(screen.getByLabelText('Meal'), 'Lunch')
    const tacoButtons = await screen.findByRole('group', { name: 'Log Beef Tacos' })
    await userEvent.click(within(tacoButtons).getByRole('button', { name: 'Log 1.5x' }))

    expect(logMeal).toHaveBeenCalledWith('111*1', 1.5, 8, 1.5, undefined)
  })

  it('logs a dish the recognizer missed from the menu search, linked to the photo', async () => {
    const rice = { ...TACOS_ON_MENU, recipe_id: '333*1', name: 'Spanish Rice' }
    recognizePhoto.mockResolvedValue(resultOf([TACOS], 7))
    getMenu.mockResolvedValue({ items: [TACOS_ON_MENU, rice] })
    logMeal.mockResolvedValue({ id: 2, calories: 250 })
    await renderAndUpload()

    await userEvent.click(await screen.findByRole('button', { name: "Not listed? Search today's menu" }))
    await userEvent.type(await screen.findByLabelText("Search today's menu"), 'rice')
    const riceButtons = screen.getByRole('group', { name: 'Log Spanish Rice' })
    // Searched dishes have no CLIP suggestion, so they start at 1x.
    await userEvent.click(within(riceButtons).getByRole('button', { name: 'Log 1x' }))

    expect(getMenu).toHaveBeenCalledWith('yahentamitsi', undefined)
    expect(logMeal).toHaveBeenCalledWith('333*1', 1, 7, undefined, undefined)  // search: no suggestion
  })

  it('does not list a dish twice when it is already a guess', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS], 7))
    getMenu.mockResolvedValue({ items: [TACOS_ON_MENU] })
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
    expect(screen.getByLabelText(/plate photo/i)).toBeDisabled()
    expect(screen.getByLabelText('Meal')).toBeDisabled()

    finishRequest(resultOf([TACOS]))
    await screen.findByText('Beef Tacos')
    expect(screen.getByLabelText(/plate photo/i)).toBeEnabled()
  })

  it('starts with one big "Snap a plate photo" button, which becomes "Retake" after a photo', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS]))
    render(<PhotoLogView hallId="yahentamitsi" />)
    expect(screen.getByLabelText(/Snap a plate photo/)).toBeInTheDocument()

    await userEvent.upload(screen.getByLabelText(/Snap a plate photo/), PLATE)
    await screen.findByText('Beef Tacos')
    expect(screen.queryByLabelText(/Snap a plate photo/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Retake plate photo')).toBeEnabled()
  })

  it('shows each guess as a numbered card with its full macros', async () => {
    recognizePhoto.mockResolvedValue(resultOf([TACOS, SALSA]))
    await renderAndUpload()

    const cards = await screen.findAllByRole('listitem')
    expect(cards[0]).toHaveTextContent('1Beef Tacos31% match')
    expect(cards[0]).toHaveTextContent('250 cal · 14g protein · 20g carbs · 12g fat per serving')
    expect(cards[1]).toHaveTextContent('2Pico de Gallo<1% match')
  })

  describe('date picker', () => {
    // Always before today, so the tests don't depend on the day they run.
    const PAST_DAY = '2026-01-05'

    it('defaults to today and does not allow later days', () => {
      render(<PhotoLogView hallId="yahentamitsi" />)

      const picker = screen.getByLabelText('Day')
      expect(picker).toHaveValue(todayOnCampus())
      expect(picker).toHaveAttribute('max', todayOnCampus())
    })

    it('sends the chosen past day with the photo, so the guesses come from that day', async () => {
      recognizePhoto.mockResolvedValue(resultOf([TACOS]))
      render(<PhotoLogView hallId="yahentamitsi" />)

      fireEvent.change(screen.getByLabelText('Day'), { target: { value: PAST_DAY } })
      await userEvent.upload(screen.getByLabelText(/plate photo/i), PLATE)

      await screen.findByText('Beef Tacos')
      expect(recognizePhoto).toHaveBeenCalledWith(PLATE, 'yahentamitsi', '', PAST_DAY)
    })

    it('re-analyzes the photo against the new day when the day changes', async () => {
      recognizePhoto.mockResolvedValue(resultOf([TACOS]))
      await renderAndUpload()
      await screen.findByText('Beef Tacos')

      fireEvent.change(screen.getByLabelText('Day'), { target: { value: PAST_DAY } })

      await screen.findByText('Beef Tacos')
      expect(recognizePhoto).toHaveBeenCalledTimes(2)
      expect(recognizePhoto).toHaveBeenLastCalledWith(PLATE, 'yahentamitsi', '', PAST_DAY)
    })

    it('files a logged dish under the chosen day and says so', async () => {
      recognizePhoto.mockResolvedValue(resultOf([TACOS]))
      logMeal.mockResolvedValue({ id: 1, calories: 250 })
      render(<PhotoLogView hallId="yahentamitsi" />)
      fireEvent.change(screen.getByLabelText('Day'), { target: { value: PAST_DAY } })
      await userEvent.upload(screen.getByLabelText(/plate photo/i), PLATE)

      const tacoButtons = await screen.findByRole('group', { name: 'Log Beef Tacos' })
      await userEvent.click(within(tacoButtons).getByRole('button', { name: 'Log 1.5x' }))

      expect(logMeal).toHaveBeenCalledWith('111*1', 1.5, 7, 1.5, PAST_DAY)
      expect(await screen.findByText('Logged 1.5x Beef Tacos (250 cal) on Jan 5.')).toBeInTheDocument()
    })

    it("searches that day's menu for a dish the recognizer missed", async () => {
      recognizePhoto.mockResolvedValue(resultOf([TACOS]))
      getMenu.mockResolvedValue({ items: [TACOS_ON_MENU] })
      render(<PhotoLogView hallId="yahentamitsi" />)
      fireEvent.change(screen.getByLabelText('Day'), { target: { value: PAST_DAY } })
      await userEvent.upload(screen.getByLabelText(/plate photo/i), PLATE)

      await userEvent.click(await screen.findByRole('button', { name: "Not listed? Search that day's menu" }))

      expect(getMenu).toHaveBeenCalledWith('yahentamitsi', PAST_DAY)
    })

    it('goes back to today when the field is cleared, and ignores a later day', async () => {
      recognizePhoto.mockResolvedValue(resultOf([TACOS]))
      await renderAndUpload()
      await screen.findByText('Beef Tacos')
      const picker = screen.getByLabelText('Day')

      fireEvent.change(picker, { target: { value: '' } })
      expect(picker).toHaveValue(todayOnCampus())
      fireEvent.change(picker, { target: { value: '2999-01-01' } })
      expect(picker).toHaveValue(todayOnCampus())
    })
  })
})
