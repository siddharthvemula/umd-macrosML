// Tests for App: the one hall picker drives both the photo screen and the menu screen.
// api.js is faked, so no backend runs.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getHalls, getMeals, getMenu, getSummary, recognizePhoto } from './api.js'
import App from './App.jsx'

vi.mock('./api.js', async (importOriginal) => ({
  ...(await importOriginal()),
  getHalls: vi.fn(),
  getMenu: vi.fn(),
  getMeals: vi.fn(),
  getSummary: vi.fn(),
  recognizePhoto: vi.fn(),
}))

const BANANA = {
  name: 'Banana', recipe_id: '111*1', station: 'Fruit', meal: 'Breakfast',
  nutrition: { calories: 109.8, protein_g: 1.3, carbs_g: 28.2, fat_g: 0.4 },
}
const CRAB_SOUP = {
  name: 'Maryland Crab Soup', recipe_id: '222*1', station: 'Soup', meal: 'Lunch', nutrition: null,
}

describe('App', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:fake-preview')
    URL.revokeObjectURL = vi.fn()
    window.localStorage.clear()
    window.localStorage.setItem('macros.photoNoticeAccepted', 'yes')
    getHalls.mockResolvedValue([
      { id: 'south_campus', name: 'South Campus' },
      { id: 'yahentamitsi', name: 'Yahentamitsi' },
    ])
    getMenu.mockImplementation(async (hall) => ({
      hall, date: '2026-10-15', items: hall === 'yahentamitsi' ? [CRAB_SOUP] : [BANANA],
    }))
    getSummary.mockResolvedValue({ date: '2026-10-15', calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0, meal_count: 0 })
    getMeals.mockResolvedValue([])
    recognizePhoto.mockResolvedValue({ hall: 'yahentamitsi', date: '2026-10-15', meal: null, guesses: [] })
  })

  it('switching the hall reloads the menu and sends later photos to the new hall', async () => {
    render(<App />)
    expect(await screen.findByText('Banana')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Dining hall'), 'yahentamitsi')
    expect(await screen.findByText('Maryland Crab Soup')).toBeInTheDocument()
    expect(screen.queryByText('Banana')).not.toBeInTheDocument()

    await userEvent.upload(screen.getByLabelText('Plate photo'), new File(['x'], 'plate.jpg', { type: 'image/jpeg' }))
    expect(recognizePhoto).toHaveBeenCalledWith(expect.any(File), 'yahentamitsi', '')
  })

  it('has a privacy section in the footer with this device\'s code', async () => {
    window.localStorage.setItem('macros.deviceId', 'abcd1234-0000-4000-8000-000000000000')
    render(<App />)

    await userEvent.click(screen.getByText('Privacy'))
    expect(screen.getByText(/only the app's developer can see them/i)).toBeVisible()
    expect(screen.getByText('abcd1234')).toBeInTheDocument()
  })

  it("shows the API's error when the halls can't load", async () => {
    getHalls.mockRejectedValue(new ApiError("Can't reach the server. Is the backend running?", null))
    render(<App />)

    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument()
  })
})
