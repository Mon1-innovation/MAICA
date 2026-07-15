<h1 align="center">MAICA-Illuminator</h1>
<div align="center">
<img src="https://maica.monika.love/assets/maica-mtts-finish-p.png" width=150>
</div>

***

<p align="center"><a href="/README.md">中文</a> | English</p>

This is the index page of MAICA, you are now at MAICA backend repo.

Full instructions of MAICA can be found at https://maica.monika.love/.

Quickstarting and terms are at https://maica.monika.love/tos.

MAICA backend repository is https://github.com/Mon1-innovation/MAICA.

MAICA backend compact branch repository is https://github.com/Mon1-innovation/MAICA_Server_Submod.

MAICA Submod frontend repository is https://github.com/Mon1-innovation/MAICA_ChatSubmod.

LIA branch of MAICA core model is at https://huggingface.co/edgeinfinity/MAICAv0-LIA-72B.

LOA branch of MAICA core model is at https://huggingface.co/edgeinfinity/MAICAv0-LOA-7B.

MAICA-MTTS Submod frontend repository is https://github.com/Mon1-innovation/MAICA_MttsSubmod.

MAICA-MTTS repository is https://github.com/Mon1-innovation/MAICA_MTTS.

MAICA-MTTS model is at https://huggingface.co/edgeinfinity/MTTSv0-VoiceClone.

Basic datasets of MAICA are at https://huggingface.co/datasets/edgeinfinity/MAICA_ds_basis.

MAICA related documents are at https://github.com/Mon1-innovation/MAICA/tree/main/document.

## Quick start

MAICA requires Python 3.12 or newer and supports Windows and Linux. The core and MFocus models are separately deployed OpenAI-compatible Responses API endpoints. MySQL/MariaDB is recommended for public services; SQLite is supported for local testing.

```bash
python -m pip install -e .
maica -t create
# Edit .env and configure MAICA_IS_REAL_ENV, databases, MCORE, and MFOCUS.
maica -e .env
```

WebSocket and HTTP listen on ports 5000 and 6000 by default. See `maica/env_basis`, `document/Backend Deployment.md`, and `document/API Documents.md` for configuration and protocol details.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check maica tests examples
```

Scripts in `examples/` are manual integration checks requiring real external services. Public deployments should terminate TLS at a reverse proxy, prefer the HTTP `Authorization: Bearer` header, protect `maica/keys/prv.key`, verify NVWatcher SSH host keys, and configure `MAICA_VISION_HOST_ALLOWLIST`.
