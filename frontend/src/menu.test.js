// Tests for the menu grouping helper in menu.js.

import { describe, expect, it } from 'vitest'
import { groupByMeal, searchMenu } from './menu.js'

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

describe('searchMenu', () => {
  const nutrition = { calories: 100 }
  const item = (recipe_id, name, meal, withNutrition = true) => ({
    recipe_id, name, meal, station: 'Grill', nutrition: withNutrition ? nutrition : null,
  })
  const MENU = [
    item('1*1', 'Spanish Rice', 'Lunch'),
    item('1*1', 'Spanish Rice', 'Lunch'), // same dish at a second station
    item('2*1', 'Fried Rice', 'Dinner'),
    item('3*1', 'Rice Pudding', 'Lunch', false), // no nutrition
    item('4*1', 'Brown Rice', 'Lunch'),
  ]

  it('matches anywhere in the name, ignoring case, each dish once', () => {
    expect(searchMenu(MENU, '  RICE ').map((d) => d.recipe_id)).toEqual(['1*1', '2*1', '4*1'])
  })

  it('keeps only the chosen meal and skips dishes already guessed', () => {
    const found = searchMenu(MENU, 'rice', { meal: 'lunch', excludeIds: ['1*1'] })
    expect(found.map((d) => d.name)).toEqual(['Brown Rice'])
  })

  it('returns nothing for an empty query and stops at the limit', () => {
    expect(searchMenu(MENU, '   ')).toEqual([])
    expect(searchMenu(MENU, 'rice', { limit: 2 })).toHaveLength(2)
  })
})
