// One progress ring on the "Today" dashboard (e.g. Protein: 63g of 150g). Drawn with plain
// SVG, no chart library. Display only: MacroTotals passes in the numbers.

// The ring's size inside its 80x80 drawing box. The browser scales the box to fit the screen.
const RADIUS = 34
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/**
 * A ring that fills toward a daily goal, with the amount left (or over) underneath.
 *
 * How the fill works: the colored circle's outline is drawn as one dash as long as the whole
 * circle (strokeDasharray), then shifted back (strokeDashoffset) by the part not reached yet.
 * At 40% of the goal, 60% of the outline is shifted out of view.
 *
 * @param {{label: string, value: number, goal: number, unit: string, tone: string}} props
 *   value: today's total. goal: the daily target. unit: "" or "g". tone: which macro color
 *   to use ("calories", "protein", "carbs" or "fat").
 * @returns {JSX.Element}
 * @example <MacroRing label="Protein" value={63.3} goal={150} unit="g" tone="protein" />
 *   // ring 42% full, "63g" in the middle, "87g left" under it
 */
export default function MacroRing({ label, value, goal, unit, tone }) {
  const rounded = Math.round(value)
  // Capped at a full ring: past the goal, the "over" label tells the rest.
  const fraction = Math.min(value / goal, 1)
  const isOver = rounded > goal
  const difference = Math.abs(goal - rounded)

  return (
    <li className={isOver ? `macro-ring macro-ring--${tone} macro-ring--over` : `macro-ring macro-ring--${tone}`}>
      {/* role="progressbar" tells screen readers this is "63 of 150", since they can't see the ring. */}
      <div
        className="macro-ring-chart"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={goal}
        aria-valuenow={rounded}
        aria-valuetext={`${rounded}${unit} of ${goal}${unit}`}
      >
        <svg viewBox="0 0 80 80" aria-hidden="true">
          <circle className="macro-ring-track" cx="40" cy="40" r={RADIUS} />
          {/* Not drawn at 0: a round line end would still show as a dot. */}
          {fraction > 0 && (
            <circle
              className="macro-ring-fill"
              cx="40"
              cy="40"
              r={RADIUS}
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - fraction)}
            />
          )}
        </svg>
        <span className="macro-ring-center">
          <span className="macro-value">{`${rounded}${unit}`}</span>
          <span className="macro-goal">{`/ ${goal}${unit}`}</span>
        </span>
      </div>
      <span className="macro-label">{label}</span>
      {/* Over the goal gets an icon and words, not just a color change. */}
      <span className="macro-remaining">
        {isOver ? `⚠ ${difference}${unit} over` : `${difference}${unit} left`}
      </span>
    </li>
  )
}
