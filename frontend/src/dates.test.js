// Tests for dates.js: campus "today" and the short day label.

import { describe, expect, it } from 'vitest'
import { formatDay, todayOnCampus } from './dates.js'

describe('todayOnCampus', () => {
  it('uses Eastern time, so late evening in Maryland is still that day', () => {
    // 03:30 UTC on Nov 11 is 10:30pm on Nov 10 in Maryland.
    expect(todayOnCampus(new Date('2026-11-11T03:30:00Z'))).toBe('2026-11-10')
  })

  it('returns the YYYY-MM-DD form the date input and the API use', () => {
    expect(todayOnCampus(new Date('2026-11-10T17:00:00Z'))).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})

describe('formatDay', () => {
  it('turns an ISO date into a short label', () => {
    expect(formatDay('2026-11-03')).toBe('Nov 3')
  })
})
