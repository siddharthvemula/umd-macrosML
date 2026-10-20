// What you see after tapping a portion button. A success is a small toast that floats at the
// bottom of the screen and fades out (useMealLogger removes it after 3 seconds), so it never
// pushes the page around. An error stays as a red box in the page until the next log.
// Shared by the menu and photo screens.

/**
 * Shows the last log's result, or nothing.
 *
 * @param {{result: {ok: boolean, text: string, id: number}|null}} props - result from useMealLogger().
 * @returns {JSX.Element|null}
 * @example <LogBanner result={{ ok: true, text: 'Logged 1x Banana (110 cal).', id: 1 }} />
 *   // a "✓ Logged 1x Banana (110 cal)." toast at the bottom of the screen
 */
export default function LogBanner({ result }) {
  if (!result) return null
  if (!result.ok) {
    return (
      <p className="notice notice--error" role="alert">
        {result.text}
      </p>
    )
  }
  // A new key for each log makes React draw a fresh toast, which restarts the fade-in animation.
  return (
    <p key={result.id} className="toast" role="status">
      <span className="toast-check" aria-hidden="true">✓</span>
      <span>{result.text}</span>
    </p>
  )
}
