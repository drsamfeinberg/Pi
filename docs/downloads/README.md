# Pi prototype downloads

- [Generation fix for existing workspace](Pi-Workspace-Generation-Fix.zip): excludes legacy demo evidence, clarifies failed generation, adds case/source controls and distinguishes Ollama errors. Apply the patch inside the existing workspace folder; it preserves private-data and .venv. See the included WORKSPACE_README.md.
- [Shared case workspace for Mac](Pi-Shared-Workspace-Mac.zip): saved cases, individual worker/clinician logins, clinic chart template, review and direct Jane handoff. Read its WORKSPACE_README.md. Start via Python in Terminal; no `.command` launcher is needed. A fictional workflow test needs only Python 3.
- [Chrome extension ZIP](pi-chrome-web-store-review.zip), version 0.3.0: shared-case bridge plus the earlier document workspace. Replace the existing extension folder contents and Reload, or Load unpacked on its root manifest.json folder.
- [Earlier local Mac service ZIP](Pi-Local-Service-Mac.zip): separate transcription/drafting service. Stop it before starting the shared workspace on the same port. It is not the shared case application.

The shared workspace package includes code and the section names of the uploaded clinic template. No source patient files, identifiers, case databases, passwords or default clinical findings are bundled. Full Mac inference, private remote access and live Jane field compatibility need testing. The first fictional workflow test does not use AI. The extension has not been approved by the Chrome Web Store. Companion SHA-256 files record package checksums.
