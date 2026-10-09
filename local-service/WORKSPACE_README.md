# Pi shared case workspace — feasibility prototype

This application stores cases and evidence on the clinic computer, gives workers and clinicians separate logins, generates several reports from the same case, records edits/approvals and hands approved drafts directly to the Jane bridge. The supplied clinic chart’s 29 sections are configured once. The five additional uploads are included: detailed PI SOAP (17 sections), attending physician, DUD/LOE, final narrative and bilingual lien/assignment form. The compact SOAP, imaging and cover-letter templates remain available. Clinical reports have no sample findings, dates, scores, diagnosis lists or billing values prefilled. The lien preserves the supplied fixed English/Spanish wording; its draft and approval do not execute or attest signatures. Only section names are included; no patient identifiers, sample values or default clinical findings are bundled.

## Quick feasibility test — no AI setup required

1. Download and unzip **Pi-Shared-Workspace-Mac.zip**. Open Terminal, type `cd ` (with the space), drag the extracted **Pi-Shared-Workspace** folder into Terminal and press Return.
2. Run `python3 workspace_server.py`. If Python 3 is missing, install Python 3 from https://www.python.org/downloads/macos/ first. The app itself uses Python's standard library; no unsigned `.command` launcher is required.
3. Open the local address printed in Terminal on the **same Mac**. First startup prints generated passwords for `clinician` and `worker`. Keep them private; they are not Jane credentials. Keep Terminal open. If an older Pi service occupies port 8765, stop that task-started service with Control-C before starting this workspace.
4. Log in as `worker` and click **Create fictional feasibility case**. The imported 29-section template is filled from fictional source headings; absent findings are explicitly labelled. This test uses no AI and is not clinical documentation.
5. Use another browser profile or private window to log in as `clinician`. Open the worker's case, review the source passages and click **Clinician: approve unsigned draft**. The worker cannot approve it. Reloading preserves the saved case.
6. Update Chrome to the accompanying Pi extension **0.3.0**. Open a fictional Jane test patient and the matching clinic evaluation template. Click Pi → **Open shared-case bridge**, sign in to the workspace and select the approved report. **Load approved report**, scan, map the matching empty fields, confirm patient/encounter and fill. Start by mapping just Chief Complaint. Click **Remember this template mapping** to reuse matching field labels on later scans; verify each suggested destination. Inspect the inserted text and save only through Jane's normal controls.

The bridge re-fetches approval before insertion and stops if the case version changed. This validates the direct transfer without downloading JSON. Scanning and filling must be tested against the real Jane editor; the generic DOM adapters do not establish EHR persistence. Existing text is skipped. No automatic signature, save or email is implemented.

## Enable real transcription and AI drafting

If the earlier local-service installation is already complete, stop it and start this workspace using its virtual environment:

```
.venv/bin/python workspace_server.py
```

If not installed, with Homebrew already available (https://brew.sh), run these commands from the workspace folder in Terminal:

```sh
brew install python@3.11 ollama
"$(brew --prefix python@3.11)/bin/python3.11" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
brew services start ollama
ollama pull qwen3:4b
.venv/bin/python -c 'from faster_whisper import WhisperModel; WhisperModel("small", device="cpu", compute_type="int8")'
.venv/bin/python workspace_server.py
```

Setup downloads the models once. Drafting and transcription then run locally. Qwen3 4B is selected for the user's 8 GB Mac; close unnecessary apps, use a short recording and selected encounter documents first. This hardware's actual model performance has not been verified. Model input includes patient/encounter context and quoted source evidence. Quotes are checked against uploaded text, but model accuracy and interpretation still require clinician verification.

Upload a short WebM/MP4 recording, click **Transcribe locally**, verify the transcript and **Verify and add notes**. Upload searchable PDFs/TXT as clinical notes, police reports or radiologist reports. Scans need OCR. Choose **Template reference** for unfilled templates; they are excluded from generation. Select one report first, then generate more from the same saved evidence. Blank sections require supported clinician input or an explanation of missing information. Diagnoses, consent, examination results and treatment decisions must not come from examples or template boilerplate.

## Remote worker trial

This app is **not publicly deployed**. The loopback address reaches only the computer running it. For a real Colombia-worker trial, install Tailscale from https://tailscale.com on the clinic computer and the worker's computer, authorize their private access and use Tailscale Serve with HTTPS. Do not use public Funnel, open router ports or bind this prototype to all network interfaces.

With the workspace running locally, configure the private gateway:

```
tailscale serve --bg http://127.0.0.1:8765
```

Note its private HTTPS URL. Restart the workspace in Terminal with that exact origin, for example:

```
PI_PUBLIC_ORIGIN=https://your-clinic-machine.your-tailnet.ts.net .venv/bin/python workspace_server.py
```

Use your actual URL, not the example. Open that URL in your browser and have the worker do the same through authorized Tailscale access. This remote gateway setup has not been exercised here. Give each worker an individual account using **Add a worker account**, assign cases to them and share initial credentials through your established private channel. Workers can view only their assigned cases; the clinician can view and approve all clinic cases.

The remote Jane bridge asks for extension access only to the workspace HTTPS origin you enter. It authenticates with the worker's workspace account, fetches assigned cases and loads approved reports. No Jane password or browser session cookie is requested.

## Storage and limits

Cases, extracted source text, reports and an action history persist in `private-data/cases.sqlite3` in this folder. The folder has owner-only permissions; the database is not application-encrypted. Passwords are salted PBKDF2 hashes. Sessions last up to eight hours. Audio files are temporary and deleted after processing; only a verified transcript added as a source is retained. Uncollected completed jobs expire after 15 minutes. Do not upload this folder or its private-data directory to GitHub.

This prototype is for fictional/de-identified feasibility testing. Production use needs appropriate hosting, access revocation, backups, encryption and patient-data handling arrangements; those are not implemented by this package. Browser case changes use version checks to avoid silently overwriting another user's work. Source additions clear previous approvals; editing a report clears its approval. Other selected report approvals remain intact until their content or evidence changes.

Stop with Control-C. Keep the folder to retain cases. Subsequent startup uses the existing usernames/passwords. To reset a forgotten workspace password locally, stop the server and run `python3 workspace_server.py --reset-password clinician`, then restart. Never share clinician credentials with workers.

## Evidence from development

Browser tests exercised worker intake, the 29-section template, clinician-only approval, saved cases after reload, PDF parsing and the bridge's changed-case check. Server tests checked worker case isolation, approval restrictions, conflicting evidence, template-reference exclusion, batch generation with model stubs and concurrent editing. Full model inference, actual Mac installation, private remote access and Jane's live editor still require the staged trial above.

## Existing case shows old fictional text after generation

The fictional test note is now automatically excluded from local AI evidence, including copies created by older releases. Expand a source in Evidence to see whether it is included; template references and the supplied demo note cannot be used as AI evidence. Use **Edit case label / encounter** to give an existing test case the appropriate case label and evaluation date without re-uploading evidence.

A failed generation clearly labels the previous saved draft and reports the error. It never counts the old fictional text as the new AI result. New reports indicate whether they came from local AI or source-heading matching. Approval of an old fictional draft is blocked once new case evidence has been added.

For an existing installation, stop Pi with Control-C, keep Terminal in your existing workspace folder and extract the small update there:

```sh
unzip -o ~/Downloads/Pi-Workspace-Generation-Fix.zip -d .
python3 workspace_server.py
```

The patch contains only application code and instructions. It does not contain or replace `private-data` or `.venv`; your cases, uploads and passwords stay in place. If you normally launch with `.venv/bin/python`, use that same Python command after updating. Sign in again and reload the page. Do not replace or delete the entire existing workspace folder.

Check `ollama list` in another Terminal window. A working Whisper transcription does not establish that the Ollama drafting model is available. The configured model is `qwen3:4b` unless PI_MODEL is set. Updated errors distinguish a stopped/unreachable service, missing model, model run failures and incomplete JSON output. Start Ollama and install the specified model if missing. If a model-output error occurs, try the compact SOAP report and a short, verified note first. Missing or unverified clinical findings remain blank.

## Case chronology and documentation guidance

The encounter field is the target report/visit date, not a date filter. Included records from earlier or later dates may support relevant case history; dated examination results must not be represented as current findings. The model is instructed to use partial evidence, translate Spanish responses with original-language source quotations, and distinguish patient goals from clinician plans. Large templates extract evidence in groups of up to three labeled sections. These are prompt and orchestration changes, not a fine-tuned model or proof of improved real-world inference.

The drafting prompt includes a general personal-injury review guide covering chronology, source attribution, SOAP, DUD/LOE and narrative reports. It is not a verified current North Carolina legal rule set. North Carolina lien, assignment, attestation and billing requirements must be checked against current official sources before being encoded as requirements; no automated compliance claim is made. Reference points for future verification include NC General Statutes 44-49 and 44-50 at https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_44/GS_44-49.html and https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_44/GS_44-50.html. Access to those sources was blocked in the development environment during this update; their text was not retrieved or verified.

Scanned PDFs and handwritten intake forms still require OCR/visual extraction and verification. A searchable police report does not make a separate scanned intake readable. This update does not add OCR. For a feasibility test, upload verified readable intake text as clinical evidence. Clinical source answers may support subjective sections without supporting objective findings, diagnoses or a prescribed treatment plan.

## Completed report examples: writing profiles

The completed example packet was reviewed to create `report_writing_profiles.json`, a patient-free set of report-specific instructions. It is included in every clinical model request: clear sectioned prose, actual dated comparisons, task-specific DUD/LOE descriptions, chronological attending/final narratives, attributed imaging summaries and concise cover letters. Sample cases, measurements, diagnoses, fee schedules, signature blocks, literature claims and provider decisions are not bundled as reusable facts. This is prompt-based guidance, not model fine-tuning or proof of clinical accuracy.

The workspace now also offers MRI Analysis Report and Itemized Billing Statement — source summary draft. MRI output summarizes existing written reports and clinician interpretations; it does not read diagnostic images independently. Billing output copies cited ledger entries and reported totals; it does not issue invoices, choose CPT units, reconcile ledgers, or calculate charges. The complete medical file remains a packet/reference, not a new generated clinical report or implemented PDF packet export.

If adding a completed example to a case for reference, choose **Completed example — style only, excluded from evidence**. These sources cannot be enabled as case evidence. To use a completed report as factual evidence for its own patient, classify it as clinical evidence instead. Do not upload another patient's completed reports as clinical evidence for the current case. The supplied originals stay outside the public code packages.

## Scanned forms and transcription cancellation

This release adds local visual extraction through Ollama `qwen2.5vl:3b` (override with PI_VISION_MODEL if a compatible model is deliberately selected). Install that model once in another Mac Terminal with `ollama pull qwen2.5vl:3b`. It is separate from the text drafting model and uses no paid cloud API. Images are sent only to loopback Ollama. The browser renders PDF pages; pages with fewer than 20 extracted characters use visual extraction automatically. For PDFs containing printed text plus image-based handwriting, tick **Read handwriting / checkboxes even when the PDF has printed text** before uploading. A text layer alone cannot prove handwritten answers are readable.

Visual extraction returns draft text plus uncertainty warnings. The original scanned page is shown alongside editable extracted text. Verify selected boxes, handwriting and diagram marks, then explicitly confirm and save the extraction. Until that happens, it is not available to report generation. This is review of machine extraction, not manual rewriting of the original document. Do not assume OCR accuracy from the word "complete". The local vision model's real accuracy and speed on the user's 8 GB Mac have not been measured; close unnecessary applications and begin with a short intake. Browser rendering and review gating were tested with a fictional scanned PDF and stubbed inference. No claim of completed end-to-end clinical validation is made.

Transcription now runs in `audio_worker.py` using the same Python interpreter as the server. It shows cached-model loading, decoding and processed recording minutes. **Cancel transcription** asks the authenticated server to terminate that worker. Temporary audio is owned by the parent and cleaned after termination; no partial transcript is saved. The other user's cancellation request is denied. A running-child cancellation test verifies termination and release of the local job lock. Cancellation is currently for audio jobs; report generation and visual extraction must finish or the workspace must be stopped. Keep the browser open during a job; resuming a result after a browser reload is not yet implemented.

Generated blank sections now distinguish absence of verified extracted excerpts from a draft whose quotations did not verify. These are pipeline outcomes, not proof that the patient's records contain no relevant information. The UI supplies a section-specific documentation question for clinician follow-up.

For the actual test, upload original scanned intake (review/save its extraction), police report and recording (review/save its transcript), then select one report. No assistant-prepared text file is needed. Retain the originals separately: this prototype persists verified text, not a complete archive of uploaded PDF/audio originals.

## Structured report engine diagnostics

Extraction now requests citations only (not redundant draft text), in groups of three sections, using smaller source chunks. The output parser accepts complete fenced JSON but never fills missing braces or salvages incomplete medical text. Required section objects, text and citation arrays are validated. A formatting/shape failure gets one bounded retry with concise quotation instructions and a larger output budget. Persistent failures report the stage, stop reason, output token count and character count without exposing source text or model content. There is no claim that truncation caused the user's specific earlier failure: the old error did not distinguish reasons.

Before another patient generation, use **Test report engine — fictional data** under Create reports. It exercises the actual local drafting and quotation checks using a small fictional SOAP case. It passes only if a cited subjective draft contains the supplied pain rating. It does not add evidence or reports to the selected patient case. A pass proves that tiny generation path on the Mac, not that a full case will be accurate or fit the model. A failure provides an actionable engine diagnostic. Development tests use stubbed model responses and real local HTTP/browser workflows; actual Ollama inference on the user's Mac remains unverified until this check runs.

## Verified evidence references during section drafting

The user's fictional model trace established a specific failure: extraction copied pain 7/10 correctly, but synthesis retyped its citation as 7/1:10, causing exact verification to discard an otherwise useful Subjective draft. Synthesis now receives evidence IDs (E1, E2, etc.) and returns those IDs instead of recopying quotations. The server resolves IDs to the immutable, already-verified source quotation, page and source. Unknown IDs are rejected; fabricated extraction quotations still cannot enter the verified set. This preserves exact provenance without relying on repeated character-perfect copying by the model.

Section synthesis also returns a support decision; symptom-only evidence should not produce objective findings, a diagnosis or a treatment plan. A false support decision leaves the section blank. The fictional engine check now requires the supplied subjective pain rating and blank objective/assessment/plan sections. These constraints and tests do not independently establish medical accuracy of arbitrary generated prose, which still requires clinician review. No fuzzy matching of altered clinical measurements is used.
