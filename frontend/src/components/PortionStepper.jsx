// The portion picker on every dish: − / + from 0.5x to 3x in 0.25 steps, the calories and
// macros for that amount (updated live), and a Log button. Used on the menu, the photo
// guesses and the photo screen's search. On a photo guess it starts at CLIP's suggestion.

import { useState } from 'react'
import { formatServings, macrosFor, MAX_SERVINGS, MIN_SERVINGS, stepServings } from '../portions.js'

/**
 * A serving stepper with live macros and a Log button for one dish.
 *
 * @param {{dishName: string, nutrition: object, disabled: boolean,
 *   suggestedServings?: number, onLog: (servings: number) => void}} props
 *   nutrition: per-serving calories/protein_g/carbs_g/fat_g.
 *   suggestedServings: CLIP's guess on photo results; the stepper starts there and shows
 *   "Suggested: 1x". Left out elsewhere (starts at 1x, no label).
 *   disabled: true while a log request is in flight, so a double-click can't log twice.
 * @returns {JSX.Element}
 * @example <PortionStepper dishName="Banana" nutrition={item.nutrition} disabled={false}
 *            onLog={(s) => logMeal('111*1', s)} />
 */
export default function PortionStepper({ dishName, nutrition, disabled, suggestedServings, onLog }) {
  const [servings, setServings] = useState(suggestedServings ?? 1)

  return (
    <div className="portions" role="group" aria-label={`Log ${dishName}`}>
      {suggestedServings !== undefined && (
        <span className="portion-suggested">Suggested: {formatServings(suggestedServings)}</span>
      )}
      <div className="stepper">
        <button
          type="button"
          aria-label="Fewer servings"
          disabled={disabled || servings <= MIN_SERVINGS}
          onClick={() => setServings((current) => stepServings(current, -1))}
        >
          −
        </button>
        {/* aria-live so a screen reader says the new amount after each tap. A plain span, not
            <output>: that counts as a "status" region, and the menu would have dozens of them. */}
        <span className="stepper-value" aria-live="polite">
          {formatServings(servings)}
        </span>
        <button
          type="button"
          aria-label="More servings"
          disabled={disabled || servings >= MAX_SERVINGS}
          onClick={() => setServings((current) => stepServings(current, +1))}
        >
          +
        </button>
        <button type="button" className="portion-log" disabled={disabled} onClick={() => onLog(servings)}>
          Log {formatServings(servings)}
        </button>
      </div>
      <span className="portion-macros">{macrosFor(nutrition, servings)}</span>
    </div>
  )
}
