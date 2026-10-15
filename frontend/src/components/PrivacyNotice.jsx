// The privacy notice. Other students use the app and their plate photos are saved as ML
// training data, so they're told what is kept, who sees it, and how to get it deleted.
// PrivacyDetails is the full text (shown in the page footer); PhotoNotice is the short
// version that the photo screen shows before the first upload, with an "I understand" button.

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
          Photos are saved exactly as uploaded. If your camera adds your location to photos, that is saved
          too, so you may want to turn that off in your camera settings.
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
 * The notice shown on the photo screen until the student accepts it.
 *
 * @param {{onAccept: () => void}} props - Called when "I understand" is tapped.
 * @returns {JSX.Element}
 * @example <PhotoNotice onAccept={() => setAccepted(true)} />
 */
export function PhotoNotice({ onAccept }) {
  return (
    <div className="photo-notice" role="region" aria-label="Photo privacy notice">
      <p>
        <strong>Before your first photo:</strong> your plate photos are saved to help train the dish recognizer.
      </p>
      <PrivacyDetails />
      <button type="button" onClick={onAccept}>
        I understand
      </button>
    </div>
  )
}
