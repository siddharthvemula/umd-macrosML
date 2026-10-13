// Tests for the "Today" dashboard (DashboardView + MacroTotals + LoggedMealsList).
// api.js is faked, so we control what "the server" answers and check what we sent it.

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, deleteMeal, getMeals, getSummary } from '../api.js'
import DashboardView from './DashboardView.jsx'

vi.mock('../api.js', async (importOriginal) => ({
  ...(await importOriginal()),
  getSummary: vi.fn(),
  getMeals: vi.fn(),
  deleteMeal: vi.fn(),
}))

const BANANA_LOG = { id: 1, name: 'Banana', servings: 2, calories: 219.6, protein_g: 2.6, carbs_g: 56.4, fat_g: 0.8 }
const EGGS_LOG = { id: 2, name: 'Scrambled Eggs', servings: 1, calories: 180.2, protein_g: 12.4, carbs_g: 1.9, fat_g: 13.1 }

/**
 * Builds a summary like the API's /summary from a list of logs.
 *
 * @param {object[]} logs
 * @returns {object} e.g. { calories: 399.8, protein_g: 15, ..., meal_count: 2 }
 */
function summaryOf(logs) {
  const total = (key) => logs.reduce((sum, log) => sum + log[key], 0)
  return {
    date: '2026-10-13', calories: total('calories'), protein_g: total('protein_g'),
    carbs_g: total('carbs_g'), fat_g: total('fat_g'), meal_count: logs.length,
  }
}

/**
 * Makes the fake API answer as if these dishes were logged today.
 *
 * @param {object[]} logs
 */
function serverHas(logs) {
  getSummary.mockResolvedValue(summaryOf(logs))
  getMeals.mockResolvedValue(logs)
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it("shows today's totals, rounded, and each logged dish", async () => {
    serverHas([BANANA_LOG, EGGS_LOG])
    render(<DashboardView refreshKey={0} />)

    expect(await screen.findByText('400')).toBeInTheDocument() // 219.6 + 180.2 calories
    expect(screen.getByText('15g')).toBeInTheDocument() // 2.6 + 12.4 protein
    expect(screen.getByText('Banana')).toBeInTheDocument()
    expect(screen.getByText('2x · 220 cal')).toBeInTheDocument()
    expect(screen.getByText('Scrambled Eggs')).toBeInTheDocument()
  })

  it('shows zeros and a friendly message on a day with nothing logged', async () => {
    serverHas([])
    render(<DashboardView refreshKey={0} />)

    expect(await screen.findByText('Nothing logged yet today.')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getAllByText('0g')).toHaveLength(3)
  })

  it("shows the error when the server can't be reached", async () => {
    getSummary.mockRejectedValue(new ApiError("Can't reach the server. Is the backend running?", null))
    getMeals.mockResolvedValue([])
    render(<DashboardView refreshKey={0} />)

    expect(await screen.findByText("Can't reach the server. Is the backend running?")).toBeInTheDocument()
  })

  it('reloads when refreshKey changes (a dish was logged on the menu)', async () => {
    serverHas([BANANA_LOG])
    const { rerender } = render(<DashboardView refreshKey={0} />)
    await screen.findByText('Banana')

    serverHas([BANANA_LOG, EGGS_LOG])
    rerender(<DashboardView refreshKey={1} />)

    expect(await screen.findByText('Scrambled Eggs')).toBeInTheDocument()
    expect(getMeals).toHaveBeenCalledTimes(2)
  })

  it('deletes a dish and shows the totals the server recalculated', async () => {
    serverHas([BANANA_LOG, EGGS_LOG])
    deleteMeal.mockResolvedValue(null)
    render(<DashboardView refreshKey={0} />)
    await screen.findByText('Banana')

    serverHas([EGGS_LOG]) // what the server returns after the delete
    await userEvent.click(screen.getByRole('button', { name: 'Delete Banana' }))

    expect(deleteMeal).toHaveBeenCalledWith(1)
    expect(await screen.findByText('180')).toBeInTheDocument()
    expect(screen.queryByText('Banana')).not.toBeInTheDocument()
  })

  it('disables the Delete button while the request is in flight, so a double-click deletes once', async () => {
    serverHas([BANANA_LOG])
    // A promise we resolve by hand, to freeze the request "in flight".
    let finishRequest
    deleteMeal.mockReturnValue(new Promise((resolve) => (finishRequest = resolve)))
    render(<DashboardView refreshKey={0} />)
    const deleteButton = await screen.findByRole('button', { name: 'Delete Banana' })

    await userEvent.click(deleteButton)
    expect(deleteButton).toBeDisabled()
    await userEvent.click(deleteButton)

    serverHas([])
    finishRequest(null)
    expect(await screen.findByText('Nothing logged yet today.')).toBeInTheDocument()
    expect(deleteMeal).toHaveBeenCalledTimes(1)
  })

  it("keeps the dish and explains why when a delete fails", async () => {
    serverHas([BANANA_LOG])
    deleteMeal.mockRejectedValue(new ApiError('Meal log 1 not found.', 404))
    render(<DashboardView refreshKey={0} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete Banana' }))

    expect(await screen.findByText("Couldn't delete Banana: Meal log 1 not found.")).toBeInTheDocument()
    expect(screen.getByText('Banana')).toBeInTheDocument()
  })
})
