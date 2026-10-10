# Contributor notes for Codex

This repository contains a SimulIDE desktop fork and its optional classroom tutor service.

## Structure
- `src/gui/aiassistant.*`, `aicontext.*`, `airender.h`: desktop tutor UI, circuit context, and rendering.
- `server/`: Flask classroom service, teacher interface, quiz/assignment workflow, knowledge retrieval, and tests.
- `scripts/`: build helpers; `.github/workflows/`: Windows build workflow.
- Keep the OpenAI API key on the teacher/server machine. Never add credentials, classroom databases, student transcripts, or private uploaded documents to source control.
- Do not change the upstream SimulIDE licensing notices. Before proposing public distribution, review the GPL/AGPL obligations for this fork and included components.

## Validation
- Server suite: `python -m unittest discover -s server -p 'test_*.py'` (install `server/requirements.txt` first).
- Native tests and build details: see `VALIDATION.md` and `scripts/build-linux.sh` / `scripts/build-windows.ps1`.
- Do not claim a Windows build or live OpenAI request was tested unless actually run.

Keep student-facing Slovenian clear and beginner-friendly. Make teacher actions and student-visible lesson states explicit. Preserve lesson-level separation of student conversations and submitted work.
