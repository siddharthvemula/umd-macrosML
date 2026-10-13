// Runs before every Vitest test file. Adds DOM matchers like toBeInTheDocument() and
// clears rendered components and mocks between tests so tests can't affect each other.

import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
