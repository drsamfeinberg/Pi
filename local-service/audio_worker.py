"""Disposable transcription process; parent owns temporary audio and cancellation."""
import json
from pathlib import Path
import sys
import pi_service as ai


def emit(value):
    print(json.dumps(value), flush=True)


if __name__ == '__main__':
    try:
        result = ai.transcribe(Path(sys.argv[1]).read_bytes(), sys.argv[2],
                               lambda stage: emit({'stage': stage}))
        emit({'result': result})
    except Exception as error:
        emit({'error': str(error) if isinstance(error, ValueError) else
              'Transcription failed. Check the cached Whisper model and recording format.'})
        sys.exit(1)
