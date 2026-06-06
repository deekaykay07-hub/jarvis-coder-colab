# Hacker1

**Hacker1.ipynb** — Pre-configured Colab T4 notebook that runs **qwen2.5-coder:7b** as a powerful unrestricted coder backend for the JARVIS red team UI.

## What it does
- Forces T4 GPU runtime
- Installs **zstd first** + GPU debs (`pciutils`, `cuda-drivers`, sets `LD_LIBRARY_PATH`)
- Installs and starts Ollama cleanly
- Pulls `qwen2.5-coder:7b` (excellent 7B coder) and creates the alias `hacker1`
- Provides ngrok or pinggy tunnel to expose the Ollama API publicly
- Includes anti-OOM settings (4k ctx, modest generation length) that work safely on T4 16 GB
- Gives you the exact public URL + model name to paste into your local JARVIS Kali UI

## Quick usage
1. Upload `hacker1.ipynb` to Google Colab.
2. Runtime → Change runtime type → **T4 GPU**.
3. Run cells from top to bottom.
4. In the "Pull Hacker1" cell it is already set to:
   ```python
   MODEL = "qwen2.5-coder:7b"
   ```
   (It also does `ollama cp ... hacker1`)
5. Run a tunnel cell (ngrok recommended — you only need a free authtoken once).
6. Copy the printed `https://...` URL.
7. In your local `jarvis_kali_ui.py`:
   - Settings → Ollama Base URL = the URL you copied
   - Model Name = `hacker1`
   - Test Connection
8. Use the Chat + Scans tabs as usual. You now have a much stronger coding brain.

## Files
- `hacker1.ipynb` — the notebook (this is the one you asked for)
- `hacker1.md` — this file

The previous more generic notebook (`jarvis-power-coder-colab.ipynb`) is still there if you want to easily switch models later.

## Why qwen2.5-coder:7b?
It is currently one of the strongest 7B-class coding models. Great at:
- Writing clean PoCs and one-liners
- Analyzing scan output
- Producing step-by-step red team plans
- Following the structured "RUN:" format the JARVIS UI parses

It is less "wild" than some pure Dolphin uncensored models but extremely capable for the pentest/coding workflow.

## OOM prevention (already built in)
- 7B Q4-ish quant on T4 is very comfortable.
- UI already sends `num_ctx: 4096`.
- The notebook shows `nvidia-smi` after load so you can see usage.
- If you ever OOM, just restart the Colab runtime and re-run the first few cells.

## Cleanup
The last cell stops the tunnel + Ollama. For a completely clean T4, use "Runtime → Factory reset runtime".

Run only on systems you have explicit authorization to test.

Enjoy the upgraded Hacker1 brain.