// Tests for the menu screen (MenuView + MenuList). Switching halls is tested in App.test.jsx. The whole api.js module is replaced
// with fakes, so these run without a backend and we control every answer.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

const GRILLED_CHEESE = {
  name: 'Grilled Cheese', recipe_id: '333*1', station: 'Grill', meal: 'Lunch',
  nutrition: { calories: 350, protein_g: 14, carbs_g: 30, fat_g: 19, serving_size: '1 each' },
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

  it('puts each station in a closed, collapsible section with its dish count', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP, GRILLED_CHEESE]))
    render(<MenuView hallId="south_campus" />)

    const fruit = (await screen.findByText('Fruit')).closest('details')
    expect(fruit).not.toHaveAttribute('open')
    expect(fruit).toHaveTextContent('Fruit1')
    expect(screen.getByText('Banana')).not.toBeVisible()

    await userEvent.click(screen.getByText('Fruit'))
    expect(screen.getByText('Banana')).toBeVisible()
  })

  it('shows the serving size under the macros', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [GRILLED_CHEESE]))
    render(<MenuView hallId="south_campus" />)

    expect(await screen.findByText('1 serving = 1 each')).toBeInTheDocument()
  })

  it('filters dishes by the search box and opens the stations that match', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP, GRILLED_CHEESE]))
    render(<MenuView hallId="south_campus" />)

    await userEvent.type(await screen.findByLabelText('Search dishes'), 'BAN')

    expect(screen.getByText('Banana')).toBeVisible()
    expect(screen.queryByText('Grilled Cheese')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Lunch' })).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('1 dish matches')
  })

  it('finds dishes by station name too', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP, GRILLED_CHEESE]))
    render(<MenuView hallId="south_campus" />)

    await userEvent.type(await screen.findByLabelText('Search dishes'), 'grill')

    expect(screen.getByText('Grilled Cheese')).toBeVisible()
    expect(screen.queryByText('Banana')).not.toBeInTheDocument()
  })

  it('says so when the search matches nothing, and clearing it brings the menu back', async () => {
    getMenu.mockResolvedValue(menuOf('south_campus', [BANANA, CRAB_SOUP]))
    render(<MenuView hallId="south_campus" />)

    const search = await screen.findByLabelText('Search dishes')
    await userEvent.type(search, 'sushi')
    expect(screen.getByText('No dishes match "sushi".')).toBeInTheDocument()

    await userEvent.clear(search)
    expect(screen.getByText('Banana')).toBeInTheDocument()
    expect(screen.getByText('Banana').closest('details')).not.toHaveAttribute('open')
  })
})
