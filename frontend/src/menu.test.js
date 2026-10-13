// Tests for the menu grouping helper in menu.js.

import { describe, expect, it } from 'vitest'
import { groupByMeal } from './menu.js'

const dish = (name, meal) => ({ name, meal })

describe('groupByMeal', () => {
  it('puts meals in day order, whatever order the API sent', () => {
    const groups = groupByMeal([dish('Pizza', 'Dinner'), dish('Eggs', 'Breakfast'), dish('Soup', 'Lunch')])
    expect(groups.map((g) => g.meal)).toEqual(['Breakfast', 'Lunch', 'Dinner'])
  })

  it('keeps dishes in their original order within a meal', () => {
    const groups = groupByMeal([dish('Pizza', 'Dinner'), dish('Salad', 'Dinner')])
    expect(groups[0].items.map((d) => d.name)).toEqual(['Pizza', 'Salad'])
  })

  it('puts a meal name it does not know after the usual ones', () => {
    const groups = groupByMeal([dish('Cake', 'Late Night'), dish('Eggs', 'Breakfast')])
    expect(groups.map((g) => g.meal)).toEqual(['Breakfast', 'Late Night'])
  })

  it('returns no groups for an empty menu', () => {
    expect(groupByMeal([])).toEqual([])
  })
})
