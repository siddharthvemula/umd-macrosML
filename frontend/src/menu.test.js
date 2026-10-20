// Tests for the menu grouping, filtering and search helpers in menu.js.

import { describe, expect, it } from 'vitest'
import { filterMenu, groupByMeal, groupByStation, searchMenu } from './menu.js'

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

describe('groupByStation', () => {
  const at = (name, station) => ({ name, station })

  it('groups dishes by station, stations in the order first seen', () => {
    const groups = groupByStation([at('Burger', 'Grill'), at('Kale', 'Salad'), at('Fries', 'Grill')])
    expect(groups.map((g) => g.station)).toEqual(['Grill', 'Salad'])
    expect(groups[0].items.map((d) => d.name)).toEqual(['Burger', 'Fries'])
  })

  it('returns no groups for no dishes', () => {
    expect(groupByStation([])).toEqual([])
  })
})

describe('filterMenu', () => {
  const items = [
    { name: 'Spanish Rice', station: 'Latin' },
    { name: 'Cheeseburger', station: 'Grill' },
    { name: 'Grilled Chicken', station: 'Entrees' },
  ]

  it('returns every dish when the search box is empty or just spaces', () => {
    expect(filterMenu(items, '  ')).toBe(items)
  })

  it('matches the name anywhere, ignoring case', () => {
    expect(filterMenu(items, 'RICE').map((d) => d.name)).toEqual(['Spanish Rice'])
  })

  it('also matches the station name', () => {
    expect(filterMenu(items, 'grill').map((d) => d.name)).toEqual(['Cheeseburger', 'Grilled Chicken'])
  })

  it('returns an empty list when nothing matches', () => {
    expect(filterMenu(items, 'sushi')).toEqual([])
  })
})
