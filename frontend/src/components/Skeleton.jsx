// Gray placeholder shapes shown while data loads ("loading skeletons"). They have the same
// layout as the real content, so the page doesn't jump when it arrives. Shared by the
// dashboard, the menu and the photo screen.

/**
 * Placeholder rings for the dashboard while today's totals load.
 *
 * @returns {JSX.Element}
 * @example {!day && <RingsSkeleton />}
 */
export function RingsSkeleton() {
  return (
    <ul className="macro-totals" aria-hidden="true">
      {[0, 1, 2, 3].map((index) => (
        <li key={index} className="macro-ring">
          <span className="skeleton skeleton--ring" />
          <span className="skeleton skeleton--text" />
        </li>
      ))}
    </ul>
  )
}

/**
 * Placeholder rows for a list of dishes while it loads.
 *
 * @param {{count?: number}} props - How many rows to draw (default 4).
 * @returns {JSX.Element}
 * @example {!menu && <RowsSkeleton count={6} />}
 */
export function RowsSkeleton({ count = 4 }) {
  return (
    <ul className="dish-list" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <li key={index} className="skeleton-row">
          <span className="skeleton skeleton--title" />
          <span className="skeleton skeleton--text" />
        </li>
      ))}
    </ul>
  )
}
