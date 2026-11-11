// Small date helpers for the photo screen's date picker. UMD's menus follow campus (Eastern)
// time, so "today" is computed there, not from the phone's own timezone.

/**
 * Today's date on campus, in the "YYYY-MM-DD" form <input type="date"> and the API use.
 *
 * @param {Date} [now] - The moment to convert (tests pass a fixed one).
 * @returns {string}
 * @example todayOnCampus(new Date('2026-11-11T03:30:00Z'))  // -> '2026-11-10' (still evening in Maryland)
 */
export function todayOnCampus(now = new Date()) {
  // The 'en-CA' locale writes dates as YYYY-MM-DD, which is exactly the format we need.
  return now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

/**
 * Turns "YYYY-MM-DD" into a short label for messages.
 *
 * @param {string} isoDate
 * @returns {string}
 * @example formatDay('2026-11-03')  // -> 'Nov 3'
 */
export function formatDay(isoDate) {
  // Noon avoids the date sliding to the previous day in timezones behind UTC.
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
