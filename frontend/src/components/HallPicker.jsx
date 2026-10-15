// The one "Dining hall" dropdown for the whole app. Display only: App owns the halls and
// the selected hall, and both the photo screen and the menu screen follow it.

/**
 * A dropdown of dining halls.
 *
 * @param {{halls: {id: string, name: string}[], hallId: string, onChange: (hallId: string) => void}} props
 * @returns {JSX.Element}
 * @example <HallPicker halls={halls} hallId="yahentamitsi" onChange={setHallId} />
 */
export default function HallPicker({ halls, hallId, onChange }) {
  return (
    <label className="hall-picker">
      Dining hall{' '}
      <select value={hallId} onChange={(event) => onChange(event.target.value)}>
        {halls.map((hall) => (
          <option key={hall.id} value={hall.id}>
            {hall.name}
          </option>
        ))}
      </select>
    </label>
  )
}
