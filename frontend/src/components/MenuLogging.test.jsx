// Tests for logging a dish from the menu screen (MenuView + MenuList + PortionButtons).
// api.js is faked, so we control what "the server" answers and check what we sent it.

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getHalls, getMenu, logMeal } from '../api.js'
import MenuView from './MenuView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()),
  getHalls: vi.fn(),
  getMenu: vi.fn(),
  logMeal: vi.fn(),
}))

const BANANA = {
  name: 'Banana', recipe_id: '111*1', station: 'Fruit', meal: 'Breakfast',
  nutrition: { calories: 109.8, protein_g: 1.3 },
}
const CRAB_SOUP = {
  name: 'Maryland Crab Soup', recipe_id: '222*1', station: 'Soup', meal: 'Lunch', nutrition: null,
}

/**
 * Renders the menu screen with Banana and Crab Soup and waits for it to load.
 *
 * @returns {Promise<HTMLElement>} Banana's group of portion buttons.
 */
async function renderMenu() {
  render(<MenuView />)
  return screen.findByRole('group', { name: 'Log Banana' })
}

describe('logging a dish', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    getHalls.mockResolvedValue([{ id: 'south_campus', name: 'South Campus' }])
    getMenu.mockResolvedValue({ hall: 'south_campus', date: '2026-10-13', items: [BANANA, CRAB_SOUP] })
  })

  it('sends the chosen portion and confirms with the logged calories', async () => {
    logMeal.mockResolvedValue({ id: 1, name: 'Banana', servings: 1.5, calories: 164.7 })
    const bananaButtons = await renderMenu()

    await userEvent.click(within(bananaButtons).getByRole('button', { name: '1.5x' }))

    expect(logMeal).toHaveBeenCalledWith('111*1', 1.5)
    expect(await screen.findByText('Logged 1.5x Banana (165 cal).')).toBeInTheDocument()
  })

  it('tells App about a successful log (so the dashboard reloads), but not a failed one', async () => {
    const onLogged = vi.fn()
    render(<MenuView onLogged={onLogged} />)
    const bananaButtons = await screen.findByRole('group', { name: 'Log Banana' })

    logMeal.mockResolvedValueOnce({ id: 1, calories: 109.8 })
    await userEvent.click(within(bananaButtons).getByRole('button', { name: '1x' }))
    await screen.findByText('Logged 1x Banana (110 cal).')
    expect(onLogged).toHaveBeenCalledTimes(1)

    logMeal.mockRejectedValueOnce(new ApiError('Server error.', 500))
    await userEvent.click(within(bananaButtons).getByRole('button', { name: '1x' }))
    await screen.findByText("Couldn't log Banana: Server error.")
    expect(onLogged).toHaveBeenCalledTimes(1)
  })

  it('offers all four portions', async () => {
    const bananaButtons = await renderMenu()

    const labels = within(bananaButtons).getAllByRole('button').map((b) => b.textContent)
    expect(labels).toEqual(['0.5x', '1x', '1.5x', '2x'])
  })

  it('gives a dish with no nutrition no buttons', async () => {
    await renderMenu()

    expect(screen.queryByRole('group', { name: 'Log Maryland Crab Soup' })).not.toBeInTheDocument()
  })

  it('disables the buttons while the request is in flight, so a double-click logs once', async () => {
    // A promise we resolve by hand, to freeze the request "in flight".
    let finishRequest
    logMeal.mockReturnValue(new Promise((resolve) => (finishRequest = resolve)))
    const bananaButtons = await renderMenu()
    const oneX = within(bananaButtons).getByRole('button', { name: '1x' })

    await userEvent.click(oneX)
    expect(oneX).toBeDisabled()

    finishRequest({ id: 1, calories: 109.8 })
    expect(await screen.findByText('Logged 1x Banana (110 cal).')).toBeInTheDocument()
    expect(oneX).toBeEnabled()
    expect(logMeal).toHaveBeenCalledTimes(1)
  })

  it("shows the server's reason when logging fails", async () => {
    logMeal.mockRejectedValue(new ApiError("No nutrition stored for recipe '111*1'.", 404))
    const bananaButtons = await renderMenu()

    await userEvent.click(within(bananaButtons).getByRole('button', { name: '2x' }))

    expect(
      await screen.findByText("Couldn't log Banana: No nutrition stored for recipe '111*1'."),
    ).toBeInTheDocument()
  })
})
