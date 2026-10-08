# Pi extension workspace — Chrome / Edge prototype, 0.3.0

Upload documents, transcribe recordings through a local Mac service, review draft reports and fill Jane from one extension workspace. The separate Pi webpage and JSON export are optional.

## Install or update

Download and unzip `pi-chrome-web-store-review.zip`. Open `chrome://extensions`, enable Developer mode and choose **Load unpacked** on the folder containing `manifest.json`. For an existing installation, replace the old folder contents and click its Reload button. Accept the additional access to the local service at `http://127.0.0.1:8765/*` if Chrome requests it. No Jane passwords or cookies are collected.

## Use

1. Start the Mac service as described in `local-service/README.md`.
2. Open the correct patient, encounter and template at `https://chiroduo.janeapp.com/admin`.
3. Click Pi → **Open workspace for this Jane tab**. Keep both tabs open.
4. Paste the local service pairing code and check the connection.
5. Enter the patient label and encounter. Upload searchable PDFs/TXT and add doctor notes. Sources can include police reports, radiologist reports, chart notes and verified transcripts.
6. For recordings, upload MP4, WebM, M4A, MP3, WAV, AAC or OGG and click **Transcribe recording locally**. Verify the transcript, then click **Add notes**. Video frames are not interpreted.
7. Select SOAP, narrative, DUD/LOE, physician, imaging or cover letter and click **Generate draft with local AI**. The offline heading matcher is also available for a simple test without model setup.
8. Review and edit every section and its source excerpts, complete missing information and reconcile discrepancies. Check the review box and approve the draft for filling. Changes revoke approval.
9. Scan the pinned Jane tab, map sections to the correct empty fields, verify patient/encounter and fill. Copying report text is an alternative. Review the inserted text and save using Jane's controls.

## Limits and validation

Sources and drafts live in the workspace tab's memory. Closing or reloading loses them. The pairing code is held in memory. Patient documents go only to the loopback service when local generation is requested; model downloads occur during setup. Audio temporary files are removed after transcription. Generated source quotes are checked against uploaded text, which does not guarantee that the model's statements or interpretation are correct. Clinician review is required.

This is template-guided drafting with local models, not a model trained on clinic patient records. Scans need OCR, recordings need verification, and medical imaging requires a written findings report. No automatic save, signature or email delivery is implemented.

Live Jane editor compatibility and persistence are unverified. Generic adapters support visible text inputs, textareas and some contenteditable editors; custom editors and iframes may need a dedicated adapter. Existing text is skipped, editor errors stop subsequent insertions, and partial insertion requires inspection. Patient context detection is limited; verify the patient and encounter yourself. Local review is a workflow label, not authenticated clinician attestation.

Browser tests validate PDF intake, direct draft review/mapping/filling with simulated Jane APIs, WebM upload routing and local AI response handling. Service tests check pairing, origins and source references using model stubs. MP4/WebM decoding was exercised with the actual audio library on Linux. Full model inference, Mac installation, Chrome Web Store approval and live Jane integration remain untested.

## Shared-case bridge

Run the shared workspace described in local-service/WORKSPACE_README.md. Open a Jane test encounter, click Pi → Open shared-case bridge, enter the clinic workspace address and your workspace login, then select an assigned case and approved report. The bridge fetches the report without JSON transfer and checks its current case version immediately before filling. If the case changed, reload and remap. For private remote HTTPS workspaces, Chrome asks for access to the exact origin entered. Workspace sessions stay in extension-page memory. The newly supplied 29-section clinic evaluation structure is bundled; sample clinical findings are not.

Template mappings can be remembered once per report type. Only section IDs and destination field labels are stored in extension localStorage, not source text or report content. Later scans preselect only uniquely matching empty fields; each fill still requires patient, encounter and mapping confirmation.

The new supplied PI SOAP, physician, DUD/LOE, final narrative and bilingual lien templates are included in the shared schema. The lien is an unsigned administrative form; no signature or notarization is performed.
