// The 0.5x / 1x / 1.5x / 2x buttons on each dish. Clicking one logs that many servings.
// The API accepts any amount up to 5; these four are just the quick choices (see DECISIONS.md).

const PORTIONS = [0.5, 1, 1.5, 2]

/**
 * A row of portion buttons for one dish.
 *
 * @param {{dishName: string, disabled: boolean, onLog: (servings: number) => void}} props
 *   disabled is true while a log request is in flight, so a double-click can't log twice.
 * @returns {JSX.Element}
 * @example <PortionButtons dishName="Banana" disabled={false} onLog={(s) => logMeal('111*1', s)} />
 */
export default function PortionButtons({ dishName, disabled, onLog }) {
  return (
    <div className="portions" role="group" aria-label={`Log ${dishName}`}>
      {PORTIONS.map((servings) => (
        <button key={servings} type="button" disabled={disabled} onClick={() => onLog(servings)}>
          {servings}x
        </button>
      ))}
    </div>
  )
}
