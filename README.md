# jarvis-coder-colab

Powerful **unrestricted coder** backends for the JARVIS red team UI, running on free **Google Colab T4 GPU**.

Both notebooks install **zstd first** + GPU debs, start clean Ollama, avoid OOM on T4, and expose a public URL for your local JARVIS UI.

## Available Notebooks

### 1. `jarvis-power-coder-colab.ipynb` (Flexible / Any Model)

- Edit one line to pull **any** 8-10B model (or direct `hf.co/...` GGUF).
- Good defaults and examples for Dolphin (uncensored), Qwen2.5-Coder, Lexi-Uncensored, etc.
- Full control over model choice.

### 2. `hacker1.ipynb` (Recommended – Pre-configured Qwen2.5-Coder 7B)

- **Locked to `qwen2.5-coder:7b`** — one of the strongest 7B coding models available.
- Automatically creates the alias `hacker1`.
- Just run the cells and use model name `hacker1` in the UI.
- Excellent at pentest planning, PoC writing, scan analysis, and structured command output.

## Quick Start (either notebook)

1. Upload the `.ipynb` to Google Colab.
2. **Runtime → Change runtime type → GPU → T4 → Save**.
3. Run cells top to bottom.
4. Run a tunnel cell (ngrok recommended).
5. Copy the printed public https URL.
6. In your local JARVIS UI:
   - Settings tab → **Ollama Base URL** = the URL
   - Model Name = `hacker1` (for the dedicated notebook) or `jarvis-coder` / your chosen tag
   - Test Connection
7. Send scans and chat as usual.

## Files in this repo

- `jarvis-power-coder-colab.ipynb` — flexible notebook (choose any model)
- `hacker1.ipynb` — dedicated qwen2.5-coder:7b notebook (alias: `hacker1`)
- `hacker1.md` — quick guide for the Hacker1 notebook
- `jarvis_kali_ui.py` — Kali Linux port of the JARVIS desktop UI
- `requirements.txt` — bleak

## Why these sizes on T4?

T4 has ~16 GB VRAM. 7-9B class models in sensible GGUF quants (Q4_K_M / Q5) + conservative context (4096) fit comfortably with room for KV cache and generation. The notebooks + UI are tuned to stay well under the limit.

## Local UI (Kali)

```bash
cd ~/Downloads/jarvis-mac-ui   # or wherever extracted
pip3 install -r requirements.txt --break-system-packages
python3 jarvis_kali_ui.py
```

Point the UI at the Colab public URL as described in the notebooks.

## Security / Legal

For **authorized red team / pentesting / security research only** on systems you own or have explicit permission to test. The models can be very unrestricted — you are responsible for usage.

## Credits

- Ollama + GGUF
- Public Colab + Ollama recipes (zstd + cuda-drivers patterns)
- Original JARVIS UI for the BTS / red team workflow

Enjoy the upgraded coder backends!