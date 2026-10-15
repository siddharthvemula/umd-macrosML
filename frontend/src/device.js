// Gives this phone/browser a permanent random ID, so the backend can keep each student's
// meals and photos separate without accounts or passwords. The ID is made the first time
// the app opens and saved in localStorage; api.js sends it with every request as the
// X-Device-Id header. Clearing the browser's site data means a new ID (a fresh, empty log).

const STORAGE_KEY = 'macros.deviceId'

// Used only when localStorage is blocked (some private-browsing modes): the ID then
// lasts until the page is reloaded, which is better than failing every request.
let fallbackId = null

/**
 * Returns this device's ID, creating and saving it on the first call.
 *
 * @returns {string} A UUID, e.g. "3f2a9c1e-7b4d-4e8a-9c2f-1a2b3c4d5e6f". Same value every call.
 * @example getDeviceId() === getDeviceId()  // -> true
 */
export function getDeviceId() {
  try {
    let id = window.localStorage.getItem(STORAGE_KEY)
    if (!id) {
      id = newUuid()
      window.localStorage.setItem(STORAGE_KEY, id)
    }
    return id
  } catch {
    fallbackId ??= newUuid()
    return fallbackId
  }
}

/**
 * Makes a random version-4 UUID.
 *
 * crypto.randomUUID() only exists on https:// or localhost pages, so testing the app on
 * a phone over plain http on home Wi-Fi would break without the getRandomValues fallback.
 *
 * @returns {string} e.g. "3f2a9c1e-7b4d-4e8a-9c2f-1a2b3c4d5e6f"
 */
function newUuid() {
  if (crypto.randomUUID) return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  // Mark it as a version 4 (random) UUID, as the standard requires; the backend checks the format.
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
