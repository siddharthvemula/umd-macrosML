// Helpers for the privacy notice (components/PrivacyNotice.jsx): the contact address,
// the short device code shown for deletion requests, and whether this device has accepted
// the photo notice, so it's shown once before the first upload instead of every visit.
// Kept in localStorage next to the device ID (device.js).

import { getDeviceId } from './device.js'

// The address students email to have their data deleted.
export const CONTACT_EMAIL = 'svemula@terpmail.umd.edu'

const ACCEPTED_KEY = 'macros.photoNoticeAccepted'

/**
 * Checks whether the photo notice was accepted on this device.
 *
 * @returns {boolean} false if never accepted, or if localStorage is blocked (we'd rather
 *   show the notice again than skip it).
 * @example hasAcceptedPhotoNotice()  // -> false on a first visit
 */
export function hasAcceptedPhotoNotice() {
  try {
    return window.localStorage.getItem(ACCEPTED_KEY) === 'yes'
  } catch {
    return false
  }
}

/**
 * Records that the photo notice was accepted.
 *
 * @example acceptPhotoNotice(); hasAcceptedPhotoNotice()  // -> true
 */
export function acceptPhotoNotice() {
  try {
    window.localStorage.setItem(ACCEPTED_KEY, 'yes')
  } catch {
    // Blocked storage: the notice just comes back next visit. The caller's state still
    // lets the student upload now.
  }
}

/**
 * The first 8 characters of this device's ID: enough to find its rows for a deletion
 * request, without showing the whole ID (which is what keeps a log private).
 *
 * @returns {string} e.g. "3f2a9c1e"
 */
export function deviceCode() {
  return getDeviceId().slice(0, 8)
}
