// Tests for the menu screen (MenuView + MenuList). The whole api.js module is replaced
// with fakes, so these run without a backend and we control every answer.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getHalls, getMenu } from '../api.js'
import MenuView from './MenuView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()), // keep the real ApiError class
  getHalls: vi.fn(),
  getMenu: vi.fn(),
}))

const HALLS = [
  { id: 'south_campus', name: 'South Campus' },
  { id: 'yahentamitsi', name: 'Yahentamitsi' },
]

const BANANA = {
  name: 'Banana', recipe_id: '111*1', station: 'Fruit', meal: 'Breakfast',
  nutrition: { calories: 109.8, protein_g: 1.3 },
}
const CRAB_SOUP = {
  name: 'Maryland Crab Soup', recipe_id: '222*1', station: 'Soup', meal: 'Lunch', nutrition: null,
}

const menuOf = (hall, items) => ({ hall, date: '2026-10-13', items })

describe('MenuView', () => {
  beforeEach(() => {
    vi.resetAllMocks() // forget the previous test's fake answers and calls
    getHalls.mockResolvedValue(HALLS)
  })

  it("shows the first hall's menu grouped by meal", async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP]))
    render(<MenuView />)

    expect(await screen.findByText('Banana')).toBeInTheDocument()
    expect(getMenu).toHaveBeenCalledWith('south_campus')
    expect(screen.getByRole('heading', { name: 'Breakfast' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Lunch' })).toBeInTheDocument()
    expect(screen.getByText('110 cal · 1.3g protein')).toBeInTheDocument()
  })

  it('labels a dish with no nutrition instead of showing blank macros', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [CRAB_SOUP]))
    render(<MenuView />)

    expect(await screen.findByText('No nutrition info')).toBeInTheDocument()
  })

  it('loads the other hall when the dropdown changes', async () => {
    getMenu.mockImplementation(async (hall) =>
      menuOf(hall, hall === 'yahentamitsi' ? [CRAB_SOUP] : [BANANA]),
    )
    render(<MenuView />)
    await screen.findByText('Banana')

    await userEvent.selectOptions(screen.getByRole('combobox'), 'yahentamitsi')

    expect(await screen.findByText('Maryland Crab Soup')).toBeInTheDocument()
    expect(screen.queryByText('Banana')).not.toBeInTheDocument()
  })

  it('says so when no menu is posted', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', []))
    render(<MenuView />)

    expect(await screen.findByText('No menu posted for today yet.')).toBeInTheDocument()
  })

  it("shows the API's error message instead of crashing", async () => {
    getHalls.mockRejectedValue(new ApiError("Can't reach the server. Is the backend running?", null))
    render(<MenuView />)

    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument()
  })
})
