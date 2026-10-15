// Tests for the menu screen (MenuView + MenuList). Switching halls is tested in App.test.jsx. The whole api.js module is replaced
// with fakes, so these run without a backend and we control every answer.

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getMenu } from '../api.js'
import MenuView from './MenuView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()), // keep the real ApiError class
  getMenu: vi.fn(),
}))

const BANANA = {
  name: 'Banana', recipe_id: '111*1', station: 'Fruit', meal: 'Breakfast',
  nutrition: { calories: 109.8, protein_g: 1.3, carbs_g: 28.2, fat_g: 0.4 },
}
const CRAB_SOUP = {
  name: 'Maryland Crab Soup', recipe_id: '222*1', station: 'Soup', meal: 'Lunch', nutrition: null,
}

const menuOf = (hall, items) => ({ hall, date: '2026-10-13', items })

describe('MenuView', () => {
  beforeEach(() => {
    vi.resetAllMocks() // forget the previous test's fake answers and calls
  })

  it("shows the hall's menu grouped by meal", async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP]))
    render(<MenuView hallId="south_campus" />)

    expect(await screen.findByText('Banana')).toBeInTheDocument()
    expect(getMenu).toHaveBeenCalledWith('south_campus')
    expect(screen.getByRole('heading', { name: 'Breakfast' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Lunch' })).toBeInTheDocument()
    expect(screen.getByText('110 cal · 1.3g protein · 28.2g carbs · 0.4g fat')).toBeInTheDocument()
  })

  it('labels a dish with no nutrition instead of showing blank macros', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [CRAB_SOUP]))
    render(<MenuView hallId="south_campus" />)

    expect(await screen.findByText('No nutrition info')).toBeInTheDocument()
  })

  it('says so when no menu is posted', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', []))
    render(<MenuView hallId="south_campus" />)

    expect(await screen.findByText('No menu posted for today yet.')).toBeInTheDocument()
  })

  it("shows the API's error message instead of crashing", async () => {
    getMenu.mockRejectedValue(new ApiError("Can't reach the server. Is the backend running?", null))
    render(<MenuView hallId="south_campus" />)

    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument()
  })
})
