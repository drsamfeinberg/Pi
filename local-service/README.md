# Pi local service for Mac

Whisper (through faster-whisper) transcribes recordings and Ollama drafts reports using templates and source excerpts. Both run locally. No paid API or Apple developer subscription is needed.

## Install

Download and unzip `Pi-Local-Service-Mac.zip`. Homebrew must already be installed from https://brew.sh. The default Qwen3 4B model uses a smaller memory budget for the user’s 8 GB Mac. Close unnecessary apps and process one case at a time. Performance varies with the Mac and source volume. The multilingual Whisper small model supports English and Spanish; check transcription accuracy before use.

Open Terminal, type `cd ` (with the space), drag the extracted **Pi-Local-Service** folder into Terminal and press Return. Then run:

```sh
bash Install.command
```

The installer uses Homebrew for Python 3.11 and Ollama, creates a local Python environment, installs pinned faster-whisper/PyAV versions, starts Ollama and downloads `qwen3:4b` and Whisper `small`. It does not send patient files. Internet access is required for these downloads. This Mac installer has been syntax-checked; actual Mac installation has not been tested here.

To start the service after installation:

```sh
bash Start.command
```

Keep Terminal open. Copy the printed pairing code into the extension. It changes when the service restarts. Use **Check local connection** in Pi. Close the service with Control-C. Ollama is started as a Homebrew service; `brew services stop ollama` stops it separately.

For a Mac with at least 16 GB memory, you can optionally install `ollama pull qwen3:8b` and start with `PI_MODEL=qwen3:8b bash Start.command`. The smaller default model can be less reliable; source verification remains necessary. Transcription unloads the drafting model first, and drafting releases the transcription model. Set `PI_WHISPER_MODEL` only after downloading that model during installation. Runtime transcription uses cached models and does not silently download them.

## Workflow

The extension sends selected source text to `127.0.0.1:8765`; the service sends it to Ollama at `127.0.0.1:11434`. Long files are processed in chunks with original page references. Exact quotations are checked before being used as drafting evidence, and output stays a draft. Matching quotations do not prove that every generated claim is supported: review names, dates, encounter scope, numbers, diagnoses, opinions and conflicting statements.

Audio upload limit is 100 MB. Supported containers include MP4 and WebM; only their audio is transcribed. Temporary audio files are deleted after processing, including failures. Results live in memory until collected, with uncollected completed results expiring after 15 minutes. Patient text is not logged or saved by this service. Other software and operating-system settings on the Mac can affect storage and networking.

The service binds to loopback, requires a per-run pairing code, rejects ordinary website origins and accepts Chrome extension origins. Do not expose it on the network. This is a local proof of concept, not a production medical-record system.

## Development checks

```sh
python -m unittest discover -s tests -p test_local_service.py
```

Run that command from the repository root. It uses model stubs to test HTTP pairing/origin controls, job collection and citation validation. Full transcription and Ollama model inference are not exercised by these tests. Whisper dependencies and actual MP4/WebM decoding were checked separately on Linux; the installer pins PyAV 16.0.1 because newer PyAV 19 removed an API needed by faster-whisper 1.2.1.
