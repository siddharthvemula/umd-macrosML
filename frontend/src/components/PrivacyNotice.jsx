// The privacy notice. Other students use the app and their plate photos are saved as ML
// training data, so they're told what is kept, who sees it, and how to get it deleted.
// PrivacyDetails is the full text (shown in the page footer); PhotoNotice is the two-line
// version that the photo screen shows before the first upload, with "Read more" and "I understand".

import { useState } from 'react'
import { CONTACT_EMAIL, deviceCode } from '../privacy.js'

/**
 * The full privacy text: what's saved, why, who sees it, and how to delete it.
 *
 * @returns {JSX.Element}
 * @example <PrivacyDetails />
 */
export function PrivacyDetails() {
  return (
    <div className="privacy-details">
      <ul>
        <li>
          <strong>Plate photos are saved.</strong> When you upload one, we keep it on our server along with
          the hall, date, meal, and the dishes you log from it.
        </li>
        <li>
          <strong>Why:</strong> saved photos are used to test and improve the dish recognizer. Only the
          app's developer can see them. They are never shown to other students.
        </li>
        <li>
          <strong>No account, no name.</strong> Your meals and photos are linked to a random code for this
          browser, not to you. Clearing this site's data starts a fresh, empty log.
        </li>
        <li>
          Before a photo is saved, we remove its hidden details, such as the location and phone model your
          camera may have added. Only the picture itself is kept.
        </li>
        <li>Only photograph your food. Keep people, faces, and ID cards out of the picture.</li>
        <li>
          <strong>Delete your data:</strong> email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> with
          your device code <code>{deviceCode()}</code> and we'll delete your photos and meal logs.
        </li>
      </ul>
      <p className="privacy-disclaimer">
        Not affiliated with UMD Dining Services. Nutrition comes from nutrition.umd.edu and may not be exact.
      </p>
    </div>
  )
}

/**
 * The notice shown on the photo screen until the student accepts it: two short lines,
 * with "Read more" opening the full PrivacyDetails text.
 *
 * @param {{onAccept: () => void}} props - Called when "I understand" is tapped.
 * @returns {JSX.Element}
 * @example <PhotoNotice onAccept={() => setAccepted(true)} />
 */
export function PhotoNotice({ onAccept }) {
  const [showDetails, setShowDetails] = useState(false)

  return (
    <div className="photo-notice" role="region" aria-label="Photo privacy notice">
      <p className="photo-notice-summary">
        Plate photos are saved to improve the dish recognizer. Only the developer sees them.
        <br />
        No account or name, location data is removed, and you can ask us to delete it anytime.
      </p>
      <button
        type="button"
        className="link-button"
        aria-expanded={showDetails}
        onClick={() => setShowDetails((shown) => !shown)}
      >
        {showDetails ? 'Show less' : 'Read more'}
      </button>
      {showDetails && <PrivacyDetails />}
      <button type="button" className="photo-notice-accept" onClick={onAccept}>
        I understand
      </button>
    </div>
  )
}
