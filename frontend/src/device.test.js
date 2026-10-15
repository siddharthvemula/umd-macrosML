// Tests for device.js: the ID is created once, kept in localStorage, and still works
// when localStorage is blocked.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { getDeviceId } from './device.js'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

describe('getDeviceId', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
  })

  it('creates a UUID once and returns the same one after', () => {
    const id = getDeviceId()
    expect(id).toMatch(UUID)
    expect(getDeviceId()).toBe(id)
    expect(window.localStorage.getItem('macros.deviceId')).toBe(id)
  })

  it('keeps an ID that was saved earlier (e.g. before a reload)', () => {
    window.localStorage.setItem('macros.deviceId', 'saved-id')
    expect(getDeviceId()).toBe('saved-id')
  })

  it('still returns a stable ID when localStorage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const id = getDeviceId()
    expect(id).toMatch(UUID)
    expect(getDeviceId()).toBe(id)
  })

  it('makes a valid UUID without crypto.randomUUID (plain-http pages)', () => {
    Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true })
    try {
      expect(getDeviceId()).toMatch(UUID)
    } finally {
      delete crypto.randomUUID // drop our own-property override, restoring the real one
    }
  })
})
