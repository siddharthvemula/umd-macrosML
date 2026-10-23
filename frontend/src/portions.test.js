// Tests for portions.js: stepping within 0.5x–3x, labels, and macros for an amount.

import { describe, expect, it } from 'vitest'
import { formatServings, macrosFor, stepServings } from './portions.js'

describe('stepServings', () => {
  it('moves by 0.25 in either direction', () => {
    expect(stepServings(1, +1)).toBe(1.25)
    expect(stepServings(0.75, -1)).toBe(0.5)
  })

  it('stays within 0.5x and 3x', () => {
    expect(stepServings(0.5, -1)).toBe(0.5)
    expect(stepServings(3, +1)).toBe(3)
  })
})

describe('formatServings', () => {
  it('labels whole and quarter amounts without trailing zeros', () => {
    expect(formatServings(1)).toBe('1x')
    expect(formatServings(0.75)).toBe('0.75x')
  })
})

describe('macrosFor', () => {
  it('multiplies by servings, whole calories and grams to 1 decimal', () => {
    const tacos = { calories: 250.4, protein_g: 14, carbs_g: 20, fat_g: 12 }
    expect(macrosFor(tacos, 1.25)).toBe('313 cal · 17.5g protein · 25g carbs · 15g fat')
  })
})
