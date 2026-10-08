# Pi — browser-only web proof of concept

This is the active iPad-oriented prototype. It needs no Apple developer account, native app, browser extension, server-side application, or paid AI service. Serve these static files from an HTTPS website to use it in Safari on an iPad. The developer environment's loopback address is not reachable from the user's iPad.

## What it demonstrates

- Searchable PDF / UTF-8 TXT import and pasted notes.
- Six template structures from the supplied samples: SOAP, final narrative, DUD/LOE, attending physician, X-ray analysis, and cover letter.
- Verbatim passage mapping based on supported section headings and aliases, with source/page/line references.
- Explicit missing information and conflicting source passages that require a choice or clinician reconciliation.
- Editable report fields, unsigned local review, and HTML/JSON export. Edits clear reviewed status.
- A fictional case demonstrating SOAP, narrative, and DUD/LOE sections without using uploaded patient data.

This is template filling, not AI synthesis. Unstructured notes are retained as sources but are not automatically interpreted. Recordings require transcripts and scanned PDFs require OCR. No diagnosis, causation, prognosis, impairment, disability rating, future-care cost, billing value, or signature is invented. Administrative fields in the example explicitly say when information is not supplied.

Imports remain in the browser tab's memory. No source documents are uploaded to the host, no browser storage is used, and there are no external services or remote CDNs in the app. PDF.js 4.10.38 is vendored locally with its Apache-2.0 license and verified npm package integrity. Reloading loses the current workspace. Exported files can contain entered information; use fictional/de-identified records for this unauthenticated proof of concept.

## Local development

```sh
cd /workspace/Pi/docs
python -m http.server 8001 --bind 127.0.0.1
```

Test commands from the repository root:

```sh
node --test tests/test_web_core.cjs
node --test tests/test_web_browser.cjs
```

The browser tests use the environment's installed Playwright and Chromium, ReportLab to generate a fictional PDF, and a temporary local static server. They emulate an iPad-sized touch viewport; actual iPad Safari has not been tested.

## Free hosting on GitHub Pages

The public repository is `drsamfeinberg/Pi`. Before publishing, review these files and the fictional fixture. Never publish source patient records, extracts, browser sessions, or credentials. Only this static `docs` folder is needed for the site.

After the site files are pushed to `main`, the repository owner can use GitHub in Safari on the iPad:

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select **main**, folder **/docs**, and **Save**.
4. Wait for GitHub's deployment to complete and use the website URL GitHub provides. Do not assume an expected URL is active before checking it.

GitHub Pages hosting for this public-repository static site does not require Apple's $99 membership. Publishing these assets is separate from creating and testing them locally. This cloud task has no GitHub Pages management tool; repository settings may require action by the owner.

## Portable single HTML file

From the repository root run:

```sh
python scripts/build_web_demo.py --output /workspace/artifacts/Pi-Web-Demo.html
```

The standalone file embeds templates, fictional examples, CSS, scripts, and the PDF parser/worker. Its Content Security Policy blocks remote network requests. It can be placed on a static HTTPS host instead of the multi-file site. Saving HTML into iPad Files or Notes is not a deployment: Files may show a Quick Look preview rather than run the app. Use a hosted Safari link for a dependable iPad workflow.

## Outside this proof of concept

Direct Jane population, email delivery, recording transcription, OCR, AI drafting, authenticated clinical storage, and production patient-data controls remain separate work. Safari/Chrome extension packaging is deferred at the user's request.
