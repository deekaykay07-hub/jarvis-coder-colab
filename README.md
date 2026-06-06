# jarvis-coder-colab

Powerful **8-10B unrestricted coder** backend for the JARVIS red team UI, running on free **Google Colab T4 GPU**.

- Installs **zstd first** + GPU debs (cuda-drivers, pciutils, LD_LIBRARY_PATH) exactly as requested
- Starts clean Ollama
- **Configurable model URL** — edit one line to pull any Ollama model or direct `hf.co/...` GGUF (including uncensored Lexi, Dolphin, Qwen2.5-Coder, etc.)
- Tuned to **avoid OOM** on T4 (~16 GB VRAM): recommends 7-9B Q4/Q5 quants + conservative context in the companion UI
- Exposes the Ollama API (port 11434) via stable public tunnel (ngrok or zero-config pinggy)
- Drop the public URL into your local **JARVIS Kali UI** (or Mac UI) Settings → instantly get a much stronger coding / pentest brain than the old 3B droplet model

The repo also bundles the JARVIS desktop UIs so everything you need is in one place.

## Quick Colab Usage (get a strong model URL for your UI)

1. Open the notebook in Colab: upload `jarvis-power-coder-colab.ipynb` or open it from this repo.
2. **Runtime → Change runtime type → GPU → T4 → Save**.
3. Run the cells top to bottom.
4. In the big "PULL YOUR MODEL" cell, set:
   ```python
   MODEL = "dolphin-llama3:8b"        # strong uncensored default
   # or
   # MODEL = "qwen2.5-coder:7b"       # excellent coder
   # MODEL = "hf.co/bartowski/dolphin-2.9-llama3-8b-GGUF:Q4_K_M"
   ```
5. Run a tunnel cell (ngrok is best — free token from ngrok.com, or use the pinggy cell).
6. Copy the printed `https://...` URL.
7. In your local JARVIS UI:
   - Settings tab → **Ollama Base URL** = the https URL you just copied
   - Model Name = `jarvis-coder` (if you created the alias) **or** the tag you pulled (`dolphin-llama3:8b`, `qwen2.5-coder:7b`, etc.)
   - Click **Test Connection**
8. Chat + send your hardware scans as usual. The 8-10B model will be dramatically better at planning, writing commands, analyzing output, etc.

The notebook also contains an optional Modelfile cell if you want a custom system prompt + lower context for even safer memory use.

## Files in this repo

- `jarvis-power-coder-colab.ipynb` — the main notebook (T4 + zstd + debs + Ollama + model pull by URL + tunnels)
- `jarvis_kali_ui.py` — the Kali Linux port of the JARVIS desktop UI (Bluetooth + WiFi hardware + approval flow)
- `requirements.txt` — bleak (for the UIs)

## Why this model size / stack?

- T4 has 16 GB VRAM. 8-9B class models in 4-bit/5-bit (GGUF Q4_K_M / Q5) + Ollama's smart layer offloading + the UI's 4k ctx fit comfortably and leave headroom.
- Larger models (13B+) or high quants on long context will OOM — the notebook warns about this and gives safe recommendations.
- "Unrestricted" models (Dolphin series, Lexi-Uncensored, etc.) + strong coders (Qwen2.5-Coder, Magicoder, etc.) give you the "more powerful unrestricted coder" you asked for.
- Ollama + GGUF is the easiest way to "just add a model's url" and have it work.

## Local UI (Kali)

See the original README in the jarvis-mac-ui.zip / jarvis-kali-ui folder, or the comments at the top of `jarvis_kali_ui.py`.

Typical run:
```bash
cd ~/Downloads/jarvis-mac-ui   # or the extracted folder
pip3 install -r requirements.txt --break-system-packages
python3 jarvis_kali_ui.py
```

Then point it at the Colab URL as described above.

## Security / Legal

This is for **authorized red teaming, pentesting, and security research only** on systems you own or have explicit written permission to test. The models are uncensored by design — you are responsible for how you use the output.

## Credits & Links

- Ollama + GGUF for the easy model loading
- The many public Colab + Ollama recipes that use the exact `zstd` + `cuda-drivers` + LD_LIBRARY_PATH pattern
- JARVIS UI originally built for the BTS / red team workflow

Pull requests and model recommendations welcome (especially new 8-10B uncensored coders that stay stable on T4).

Enjoy the upgraded JARVIS.