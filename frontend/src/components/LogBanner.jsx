// The green/red "Logged 1x Banana (110 cal)." line shown after tapping a portion button.
// Shared by the menu and photo screens.

/**
 * Shows the last log's result, or nothing.
 *
 * @param {{result: {ok: boolean, text: string}|null}} props - result from useMealLogger().
 * @returns {JSX.Element|null}
 * @example <LogBanner result={{ ok: true, text: 'Logged 1x Banana (110 cal).' }} />
 */
export default function LogBanner({ result }) {
  if (!result) return null
  return (
    <p className={result.ok ? 'notice notice--success' : 'notice notice--error'} role="status">
      {result.text}
    </p>
  )
}
