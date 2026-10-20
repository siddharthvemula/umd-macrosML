// Tests for goals.js: loading, cleaning and saving the daily macro goals.

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_GOALS, cleanGoals, loadGoals, saveGoals } from './goals.js'

describe('goals', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('uses the defaults on a first visit', () => {
    expect(loadGoals()).toEqual(DEFAULT_GOALS)
  })

  it('loads goals saved earlier', () => {
    saveGoals({ calories: 2500, protein_g: 180, carbs_g: 250, fat_g: 70 })
    expect(loadGoals()).toEqual({ calories: 2500, protein_g: 180, carbs_g: 250, fat_g: 70 })
  })

  it('replaces each bad value with its fallback and rounds the rest', () => {
    expect(cleanGoals({ calories: '2500.4', protein_g: -3, carbs_g: 'lots', fat_g: 999999 })).toEqual({
      calories: 2500, protein_g: 150, carbs_g: 225, fat_g: 65,
    })
  })

  it('falls back to the given goals, not the defaults, when one is passed', () => {
    const current = { calories: 1800, protein_g: 120, carbs_g: 200, fat_g: 60 }
    expect(cleanGoals({ calories: '', protein_g: 130 }, current)).toEqual({ ...current, protein_g: 130 })
  })

  it('uses the defaults when the saved JSON is corrupted', () => {
    window.localStorage.setItem('macros.goals', '{not json')
    expect(loadGoals()).toEqual(DEFAULT_GOALS)
  })

  it('still returns the goals when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(saveGoals({ calories: 2100, protein_g: 140, carbs_g: 230, fat_g: 60 }).calories).toBe(2100)
  })
})
