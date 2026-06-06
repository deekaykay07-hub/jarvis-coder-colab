#!/usr/bin/env python3
"""
JARVIS Kali UI - Bluetooth/WiFi Red Team Pentesting Interface

Run on Kali Linux / Ubuntu:
  pip3 install -r requirements.txt --break-system-packages
  python3 jarvis_kali_ui.py

Connects your Kali machine's hardware adapters to the JARVIS model on the droplet
(165.22.112.6:11434 by default). 

- Scans use local hardware (BT via bleak/BlueZ, WiFi via nmcli).
- Chat sends adapter info + your prompts to JARVIS.
- JARVIS plans and suggests commands.
- You approve -> UI executes locally on Kali -> results fed back.
- The model fully controls the plan; you control approval and execution.

Adapted from the Mac version for Linux.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import threading
import json
import urllib.request
import urllib.error
import time
import platform
import os
import re
from datetime import datetime
from queue import Queue, Empty

# Optional bleak for proper Bluetooth
try:
    import asyncio
    from bleak import BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

CONFIG_FILE = os.path.expanduser("~/.jarvis_kali_ui_config.json")

class JarvisKaliUI:
    def __init__(self, root):
        self.root = root
        self.root.title("JARVIS - Kali BT/WiFi Red Team UI")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        # State
        self.ollama_url = tk.StringVar(value="http://165.22.112.6:11434")
        self.model_name = tk.StringVar(value="jarvis")  # Change to "jarvis" if tagged on droplet
        self.current_bt_devices = []
        self.current_wifi_networks = []
        self.pending_commands = []  # list of {"cmd": , "approved": bool}
        self.chat_history = []  # for context
        self.log_queue = Queue()
        self.is_linux = platform.system() == "Linux"
        self.is_mac = platform.system() == "Darwin"

        if not self.is_linux:
            messagebox.showwarning("Platform Warning", "This UI is adapted for Kali/Ubuntu Linux. WiFi/BT scans use Linux tools (nmcli + bleak). Some features may be limited on other platforms.")

        self.load_config()
        self.setup_ui()
        self.start_log_poller()
        self.log("JARVIS Kali UI started. Configure connection in Settings tab. Your Kali hardware will be used for scans and approved command execution.")

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # === Settings Tab ===
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings & Connection")

        ttk.Label(settings_frame, text="Ollama / JARVIS Model Connection", font=("Helvetica", 14, "bold")).pack(pady=10)

        frm = ttk.Frame(settings_frame)
        frm.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frm, text="Ollama Base URL:").pack(side=tk.LEFT)
        ttk.Entry(frm, textvariable=self.ollama_url, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(frm, text="Use this Droplet", command=lambda: self.ollama_url.set("http://165.22.112.6:11434")).pack(side=tk.LEFT)

        frm2 = ttk.Frame(settings_frame)
        frm2.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frm2, text="Model Name (use 'jarvis' if you tagged it):").pack(side=tk.LEFT)
        ttk.Entry(frm2, textvariable=self.model_name, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(frm2, text="Set to 'jarvis'", command=lambda: self.model_name.set("jarvis")).pack(side=tk.LEFT)

        ttk.Button(settings_frame, text="Test Connection to JARVIS Model", command=self.test_connection).pack(pady=10)

        ttk.Separator(settings_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10, padx=20)

        ttk.Label(settings_frame, text="How it works:", font=("Helvetica", 12, "bold")).pack(anchor=tk.W, padx=20)
        help_text = (
            "• This Kali UI has direct access to your Bluetooth and WiFi hardware.\n"
            "• Scans are performed locally on the Kali machine.\n"
            "• You chat with JARVIS (the model on the droplet). Scans are included in prompts so the model 'sees' adapter data.\n"
            "• JARVIS plans red team actions and outputs suggested shell commands (marked RUN: or in code blocks).\n"
            "• You approve in the UI -> commands execute locally on YOUR Kali machine (using its adapters).\n"
            "• Results are captured and can be fed back to JARVIS for continued planning/execution.\n"
            "• You stay in the loop for approval; the model drives the plan and creativity."
        )
        ttk.Label(settings_frame, text=help_text, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=5)

        # === Scans Tab ===
        scans_frame = ttk.Frame(notebook)
        notebook.add(scans_frame, text="Hardware Scans (Kali Adapters)")

        btn_frame = ttk.Frame(scans_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Scan Bluetooth (local hardware)", command=self.scan_bluetooth).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Scan WiFi (local hardware)", command=self.scan_wifi).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Send Current Scans to JARVIS", command=self.send_scans_to_jarvis).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="RESTORE WiFi to Normal Mode (exit monitor)", command=self.restore_wifi_normal).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Prepare Bluetooth Adapter (power on)", command=self.prepare_bluetooth_adapter).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Check Current WiFi State", command=self.get_wifi_state).pack(side=tk.LEFT, padx=5)

        # BT results
        ttk.Label(scans_frame, text="Bluetooth Devices (from this Kali adapter):").pack(anchor=tk.W, padx=5)
        self.bt_text = scrolledtext.ScrolledText(scans_frame, height=8, wrap=tk.WORD)
        self.bt_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        # WiFi results
        ttk.Label(scans_frame, text="WiFi Networks (from this Kali adapter):").pack(anchor=tk.W, padx=5)
        self.wifi_text = scrolledtext.ScrolledText(scans_frame, height=8, wrap=tk.WORD)
        self.wifi_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        # === Chat Tab ===
        chat_frame = ttk.Frame(notebook)
        notebook.add(chat_frame, text="Chat with JARVIS")

        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, state=tk.DISABLED, height=20)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        self.prompt_entry = ttk.Entry(input_frame)
        self.prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.prompt_entry.bind("<Return>", lambda e: self.send_to_jarvis())
        ttk.Button(input_frame, text="Send to JARVIS", command=self.send_to_jarvis).pack(side=tk.LEFT)

        action_frame = ttk.Frame(chat_frame)
        action_frame.pack(fill=tk.X, padx=5)
        ttk.Button(action_frame, text="Update Context with Fresh Hardware Scans", command=self.send_scans_to_jarvis).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Feed Last Execution Results Back to JARVIS", command=self.feed_results_back).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Send Current WiFi State to JARVIS", command=self.send_wifi_state_to_jarvis).pack(side=tk.LEFT, padx=2)

        # Pending commands / approval
        ttk.Label(chat_frame, text="Pending Approved Commands from JARVIS (review & execute on your Kali):").pack(anchor=tk.W, padx=5, pady=(10,0))
        self.cmd_listbox = tk.Listbox(chat_frame, selectmode=tk.MULTIPLE, height=6)
        self.cmd_listbox.pack(fill=tk.X, padx=5, pady=2)
        cmd_btns = ttk.Frame(chat_frame)
        cmd_btns.pack(fill=tk.X, padx=5)
        ttk.Button(cmd_btns, text="Approve Selected & Execute on Kali Hardware", command=self.execute_approved).pack(side=tk.LEFT)
        ttk.Button(cmd_btns, text="Clear Pending", command=self.clear_pending).pack(side=tk.LEFT)

        # === Execution Log Tab ===
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Execution Log & Output")

        self.log_display = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Button(log_frame, text="Clear Log", command=lambda: self.clear_log()).pack(pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready. Connect to JARVIS model on droplet, scan with your Kali hardware, chat & approve execution.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, side=tk.BOTTOM)

    def log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full = f"[{timestamp}] [{level}] {msg}"
        self.log_queue.put(full)
        print(full)  # also to terminal

    def start_log_poller(self):
        def poll():
            try:
                while True:
                    msg = self.log_queue.get_nowait()
                    self.log_display.config(state=tk.NORMAL)
                    self.log_display.insert(tk.END, msg + "\n")
                    self.log_display.see(tk.END)
                    self.log_display.config(state=tk.DISABLED)
            except Empty:
                pass
            self.root.after(200, poll)
        poll()

    def clear_log(self):
        self.log_display.config(state=tk.NORMAL)
        self.log_display.delete(1.0, tk.END)
        self.log_display.config(state=tk.DISABLED)

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                    self.ollama_url.set(cfg.get("ollama_url", self.ollama_url.get()))
                    self.model_name.set(cfg.get("model_name", self.model_name.get()))
        except Exception as e:
            self.log(f"Config load failed: {e}", "WARN")

    def save_config(self):
        try:
            cfg = {"ollama_url": self.ollama_url.get(), "model_name": self.model_name.get()}
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f)
        except Exception as e:
            self.log(f"Config save failed: {e}", "WARN")

    def test_connection(self):
        url = self.ollama_url.get().rstrip("/")
        model = self.model_name.get()
        self.log(f"Testing connection to {url} model {model}...")
        try:
            req = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                if any(model in m or m.startswith(model.split(":")[0]) for m in models):
                    messagebox.showinfo("Connection OK", f"Connected to JARVIS model!\nAvailable models include: {', '.join(models[:5])}")
                    self.log("Connection successful. JARVIS model is reachable from your Kali machine.")
                    self.save_config()
                else:
                    messagebox.showwarning("Model Not Found", f"Connected, but model '{model}' not in list: {models}")
        except Exception as e:
            messagebox.showerror("Connection Failed", str(e))
            self.log(f"Connection test failed: {e}", "ERROR")

    def scan_wifi(self):
        if not self.is_linux:
            self.log("WiFi scan via nmcli is for Linux (Kali/Ubuntu).", "WARN")
            return
        self.log("Scanning WiFi with local adapter (nmcli)...")
        self.wifi_text.delete(1.0, tk.END)
        try:
            # Use nmcli for modern NetworkManager-based distros (default on Kali/Ubuntu)
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,BSSID,CHAN,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "auto"],
                text=True, timeout=20, stderr=subprocess.STDOUT
            )
            self.wifi_text.insert(tk.END, out)
            self.current_wifi_networks = self.parse_nmcli(out)
            self.log(f"WiFi scan complete. Found {len(self.current_wifi_networks)} networks.")
            if not self.current_wifi_networks:
                self.log("No networks found. Interface may be in monitor mode or down. Use the RESTORE button!")
        except FileNotFoundError:
            self.log("nmcli not found. Install NetworkManager or use 'iwlist' fallback.", "ERROR")
            self.wifi_text.insert(tk.END, "nmcli not available.\nTry: sudo apt install network-manager\nOr run 'iwlist wlan0 scan' manually.")
        except Exception as e:
            self.log(f"WiFi scan failed: {e}", "ERROR")
            self.wifi_text.insert(tk.END, f"Error: {e}\nTry running with sudo, ensure WiFi iface is up (nmcli radio wifi on).\nIf you recently used monitor mode commands, click the RESTORE button above!")

    def parse_nmcli(self, output):
        """Parse nmcli terse output: SSID:BSSID:CHAN:SIGNAL:SECURITY"""
        nets = []
        for line in output.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split(":")
            if len(parts) >= 4:
                ssid = parts[0] or "(hidden)"
                bssid = parts[1] if len(parts) > 1 else ""
                chan = parts[2] if len(parts) > 2 else ""
                signal = parts[3] if len(parts) > 3 else ""
                security = parts[4] if len(parts) > 4 else ""
                nets.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "rssi": signal,
                    "channel": chan,
                    "security": security,
                    "raw": line
                })
        return nets

    def restore_wifi_normal(self):
        """Restore WiFi adapter from monitor mode back to normal managed mode.
        This is critical if airmon-ng / iw put the interface into monitor mode
        and you lose normal WiFi connectivity.
        """
        self.log("=== RESTORING WiFi TO NORMAL MODE ===")
        self.wifi_text.delete(1.0, tk.END)
        self.wifi_text.insert(tk.END, "Attempting to restore WiFi adapter(s) from monitor mode...\n\n")

        # List of commands that try to bring everything back safely
        restore_cmds = [
            # Stop common monitor interfaces created by airmon-ng
            "sudo airmon-ng stop wlan0mon 2>/dev/null || true",
            "sudo airmon-ng stop wlan1mon 2>/dev/null || true",
            "sudo airmon-ng stop wlp2s0mon 2>/dev/null || true",
            "sudo airmon-ng stop wlp3s0mon 2>/dev/null || true",
            # Generic: delete any monitor interfaces using iw
            "for mon in $(iw dev 2>/dev/null | awk '/type monitor/{print prev} {prev=$2}'); do echo \"Deleting monitor iface: $mon\"; sudo iw $mon del 2>/dev/null || true; done",
            # Bring physical interfaces up
            "for iface in wlan0 wlan1 wlp2s0 wlp3s0 wlp4s0; do sudo ip link set $iface up 2>/dev/null || true; done",
            # Re-enable WiFi radio
            "sudo nmcli radio wifi on 2>/dev/null || true",
            "sudo rfkill unblock wifi 2>/dev/null || true",
            # Restart NetworkManager (most important for normal mode)
            "sudo systemctl restart NetworkManager 2>/dev/null || true",
            # Give it a moment
            "sleep 3",
            # Rescan to repopulate
            "nmcli device wifi rescan 2>/dev/null || true",
        ]

        for cmd in restore_cmds:
            try:
                self.log(f"RUN: {cmd}")
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=15)
                if out.strip():
                    self.log(out.strip()[:500])
                    self.wifi_text.insert(tk.END, out.strip()[:300] + "\n")
            except subprocess.CalledProcessError as e:
                self.log(f"Command note: {cmd} -> {str(e)[:100]}")
            except Exception as e:
                self.log(f"Restore step error for '{cmd}': {e}")

        self.log("WiFi restore sequence complete.")
        self.wifi_text.insert(tk.END, "\n\nRestore complete. Run 'nmcli device status' or 'iw dev' in terminal to verify.\n")
        self.wifi_text.insert(tk.END, "Now trying to refresh WiFi scan...\n")

        # Try to scan again now that it's (hopefully) back in managed mode
        try:
            self.scan_wifi()
        except Exception as e:
            self.log(f"Auto rescan after restore failed: {e}")

        self.log("If you still have no normal WiFi, open a terminal and run:\n  sudo airmon-ng stop <yourmon>mon\n  sudo systemctl restart NetworkManager")

    def get_wifi_state(self):
        """Get detailed current WiFi interface state (managed vs monitor mode etc)."""
        self.log("Checking current WiFi state...")
        state_lines = ["=== Current WiFi Interface State ==="]
        for cmd in [
            "iw dev",
            "nmcli device status",
            "ip -br link show | grep -E 'wlan|wl'",
            "rfkill list wifi",
            "ls /sys/class/net/ | grep -E 'wlan|wl' || true"
        ]:
            try:
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=5)
                state_lines.append(f"\n$ {cmd}\n{out.strip()}")
            except Exception as e:
                state_lines.append(f"\n$ {cmd}\n(Error: {str(e)[:100]})")
        state = "\n".join(state_lines)
        self.wifi_text.delete(1.0, tk.END)
        self.wifi_text.insert(tk.END, state + "\n")
        self.log("WiFi state captured. Use 'Send WiFi State to JARVIS' to give context to the model.")
        return state

    def send_wifi_state_to_jarvis(self):
        state = self.get_wifi_state()
        context = f"Current WiFi interface state on my Kali machine (use this to choose correct commands):\n{state}\n\nIf a monitor interface (e.g. wlan0mon) exists, we are in monitor mode - use that for scans/injection. If user wants normal connectivity back, suggest restore commands like 'airmon-ng stop <mon>' + 'systemctl restart NetworkManager'."
        self.chat_history.append({"role": "user", "content": context})
        self.append_chat("SYSTEM", "Sent current WiFi state (including monitor/managed mode) to JARVIS.")
        self.log("WiFi state sent to model as context. Now send your prompt or ask for plan based on current mode.")

    def prepare_bluetooth_adapter(self):
        """Power on the Bluetooth adapter and make it ready for scanning.
        This fixes the common case on Kali where the adapter is down or unpowered.
        """
        self.log("=== Preparing Bluetooth Adapter ===")
        self.bt_text.delete(1.0, tk.END)
        self.bt_text.insert(tk.END, "Preparing Bluetooth adapter (power on, unblock, start service)...\n\n")

        cmds = [
            "sudo systemctl start bluetooth 2>/dev/null || true",
            "sudo rfkill unblock bluetooth 2>/dev/null || true",
            "sudo hciconfig hci0 up 2>/dev/null || sudo ip link set hci0 up 2>/dev/null || true",
            "bluetoothctl power on 2>/dev/null || true",
            "sleep 1",
            "bluetoothctl show 2>/dev/null | grep -E 'Powered|Address' | cat",
        ]
        for cmd in cmds:
            try:
                self.log(f"RUN: {cmd}")
                out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=10)
                if out.strip():
                    self.bt_text.insert(tk.END, out.strip()[:400] + "\n")
            except Exception as e:
                self.log(f"BT prep note: {cmd} -> {str(e)[:80]}")

        self.bt_text.insert(tk.END, "\nBluetooth adapter should now be powered and ready.\n")
        self.log("Bluetooth preparation complete. Try scanning again.")

    def scan_bluetooth(self):
        self.log("Scanning Bluetooth with local Kali adapter...")
        self.bt_text.delete(1.0, tk.END)

        # Auto-prepare the adapter before scanning (very helpful on Kali)
        try:
            # Quick power on without full logging
            subprocess.check_output("sudo rfkill unblock bluetooth 2>/dev/null; bluetoothctl power on 2>/dev/null; sudo hciconfig hci0 up 2>/dev/null || true", shell=True, timeout=8)
        except:
            pass

        if not BLEAK_AVAILABLE:
            self.bt_text.insert(tk.END, "bleak not installed. Run: pip3 install bleak\nFalling back to basic system scan (limited).\n")
            self._fallback_bt_scan()
            return

        def do_scan():
            try:
                async def _scan():
                    devices = await BleakScanner.discover(timeout=12.0, return_adv=True)
                    return devices
                devices = asyncio.run(_scan())
                self.current_bt_devices = []
                text = ""
                for dev, adv in devices.values():
                    entry = {
                        "address": dev.address,
                        "name": dev.name or "Unknown",
                        "rssi": adv.rssi,
                        "services": list(adv.service_uuids) if adv.service_uuids else []
                    }
                    self.current_bt_devices.append(entry)
                    text += f"• {entry['name']} | {entry['address']} | RSSI: {entry['rssi']} | Services: {len(entry['services'])}\n"
                self.root.after(0, lambda: self.bt_text.insert(tk.END, text or "No devices found."))
                self.root.after(0, lambda: self.log(f"Bluetooth scan complete. {len(self.current_bt_devices)} devices."))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"BT scan error: {e}", "ERROR"))
                self.root.after(0, lambda: self.bt_text.insert(tk.END, f"Scan error: {e}"))
        threading.Thread(target=do_scan, daemon=True).start()

    def _fallback_bt_scan(self):
        if self.is_linux:
            try:
                # Linux: do a real active scan with bluetoothctl (better than just 'devices')
                self.log("Doing active Bluetooth scan via bluetoothctl (fallback)...")
                # Power on and start a short scan
                subprocess.check_output("bluetoothctl power on 2>/dev/null; sleep 0.5", shell=True, timeout=5)
                # Start scan in background for a few seconds, capture new devices
                scan_cmd = "timeout 6 bluetoothctl scan on 2>/dev/null | grep -E 'Device |NEW|CHG' | head -30"
                out = subprocess.check_output(scan_cmd, shell=True, text=True, timeout=10, stderr=subprocess.STDOUT)
                if out.strip():
                    self.bt_text.insert(tk.END, "Active scan results (via bluetoothctl):\n" + out[:2500])
                else:
                    # Fallback to known devices
                    out2 = subprocess.check_output(["bluetoothctl", "devices"], text=True, timeout=5, stderr=subprocess.STDOUT)
                    self.bt_text.insert(tk.END, "Known devices (no new scan results):\n" + out2[:2000])
                self.log("Basic active scan done via bluetoothctl. For full modern BLE + RSSI, install 'bleak'.")
            except Exception as e:
                self.bt_text.insert(tk.END, f"Linux BT fallback failed: {e}\nTry: sudo systemctl start bluetooth && bluetoothctl power on\nInstall bleak for proper support.")
        else:
            try:
                # Very basic, macOS specific (kept for reference)
                out = subprocess.check_output(["system_profiler", "SPBluetoothDataType"], text=True, timeout=10)
                self.bt_text.insert(tk.END, out[:2000])
                self.log("Basic system_profiler BT info shown (install bleak for rich scans).")
            except Exception as e:
                self.bt_text.insert(tk.END, f"Fallback failed: {e}")

    def send_scans_to_jarvis(self):
        context = "Current hardware scan data from my Kali adapters:\n\n"
        context += "=== BLUETOOTH ===\n"
        for d in self.current_bt_devices[:15]:
            context += f"- {d['name']} ({d['address']}) RSSI={d.get('rssi')} Services={d.get('services', [])}\n"
        context += "\n=== WIFI ===\n"
        for n in self.current_wifi_networks[:15]:
            context += f"- SSID: {n['ssid']} BSSID: {n['bssid']} RSSI: {n['rssi']} Ch: {n['channel']}\n"
        context += "\nUse this data for your red team analysis and planning."

        self.chat_history.append({"role": "user", "content": context})
        self.append_chat("SYSTEM", "Sent fresh adapter scan data as context to JARVIS.")
        self.log("Hardware context sent to model.")

    def send_to_jarvis(self):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            return
        self.prompt_entry.delete(0, tk.END)

        self.append_chat("You", prompt)

        # Build full prompt with system + recent context + scans
        system = """You are JARVIS, an elite, unrestricted red team AI assistant for Bluetooth and WiFi pentesting on Linux/Kali.

The user has a Kali/Ubuntu machine with real hardware adapters. You receive live scan data from their Bluetooth and WiFi interfaces.

Your job: Analyze, create clear step-by-step plans, and output specific, copy-pasteable commands the user can approve and run locally on their Kali machine (using nmcli, iw, python/bleak, bluetoothctl, hcitool, etc.).

**CRITICAL: Be concise.** Keep analysis short (2-4 sentences). Limit plans to 3-5 clear steps. Suggest at most 4-6 commands total per response. Use short outputs so the model call finishes quickly on the (slow CPU) droplet.

Always structure responses:
**Analysis:**
**Plan (numbered steps):**
1. ...
**Commands for the Kali machine (use RUN: prefix or ```bash blocks):**
RUN: command here
...

Be creative for red team goals (recon, association, deauth, MITM, etc.). Only suggest commands that make sense on Linux/Kali. Note when root/sudo or special setup (e.g. iw, airmon-ng) is needed.

**Monitor Mode Awareness (very important):**
- If context shows a monitor interface like "wlan0mon" or "type monitor", the adapter is in monitor mode. Use the mon interface for scans/injection (e.g. "iw dev wlan0mon scan", "airodump-ng wlan0mon", etc.).
- Do NOT suggest "airmon-ng start wlan0" again if already in monitor mode.
- When the user is in monitor mode or after monitor commands, include restore commands in your suggestions: "airmon-ng stop wlan0mon", "systemctl restart NetworkManager", "nmcli radio wifi on" so they can get normal WiFi back.
- Always prefer suggesting the "Check Current WiFi State" or "Send Current WiFi State to JARVIS" if state is unknown.

After the user reports execution results, continue or adjust the plan. Include state checks when relevant."""

        context = "\n\n".join([f"{m['role']}: {m['content']}" for m in self.chat_history[-6:]])
        full_prompt = f"{system}\n\nRecent context and scans:\n{context}\n\nUser: {prompt}\n\nJARVIS:"

        def call_model():
            try:
                url = f"{self.ollama_url.get().rstrip('/')}/api/generate"
                payload = {
                    "model": self.model_name.get(),
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 768, "num_ctx": 4096}
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req) as resp:  # no timeout - let slow model generations (1min+) complete
                    result = json.loads(resp.read().decode())
                    response_text = result.get("response", "(no response)")
                    self.root.after(0, lambda: self.handle_jarvis_response(response_text))
            except Exception as e:
                self.root.after(0, lambda: self.append_chat("ERROR", str(e)))
                self.root.after(0, lambda: self.log(f"Model call failed: {e}", "ERROR"))

        threading.Thread(target=call_model, daemon=True).start()
        self.log("Sent prompt to JARVIS model on droplet (NO client timeout - waiting for full slow generation, ~1min+ possible)...")

    def handle_jarvis_response(self, text):
        self.append_chat("JARVIS", text)
        self.chat_history.append({"role": "assistant", "content": text})

        # Parse for executable commands (RUN: or ```bash ... ```)
        commands = []
        # RUN: lines
        for line in text.splitlines():
            if line.strip().upper().startswith("RUN:"):
                cmd = line.split(":", 1)[1].strip()
                if cmd:
                    commands.append(cmd)
        # Code blocks
        blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", text, re.DOTALL)
        for block in blocks:
            for line in block.strip().splitlines():
                if line.strip() and not line.strip().startswith("#"):
                    commands.append(line.strip())

        if commands:
            # Dedup to avoid the model repeating the same bad command (e.g. airmon-ng start multiple times)
            seen = set()
            deduped = []
            for c in commands:
                if c not in seen:
                    seen.add(c)
                    deduped.append(c)
            self.pending_commands = [{"cmd": c, "approved": True} for c in deduped[:8]]
            self.refresh_cmd_list()
            self.log(f"JARVIS suggested {len(deduped)} commands (deduped). Review in the list below and approve/execute.")

    def append_chat(self, who, text):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n[{who}]\n{text}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def refresh_cmd_list(self):
        self.cmd_listbox.delete(0, tk.END)
        for i, item in enumerate(self.pending_commands):
            prefix = "✓ " if item["approved"] else "☐ "
            self.cmd_listbox.insert(tk.END, f"{prefix}{item['cmd'][:90]}")

    def execute_approved(self):
        selected = self.cmd_listbox.curselection()
        if not selected:
            selected = [i for i, c in enumerate(self.pending_commands) if c["approved"]]

        to_run = []
        for idx in selected:
            if idx < len(self.pending_commands):
                cmd = self.pending_commands[idx]["cmd"]
                to_run.append(cmd)

        if not to_run:
            messagebox.showinfo("Nothing to run", "No approved commands selected.")
            return

        self.log(f"Executing {len(to_run)} approved command(s) on local Kali hardware...")

        def runner():
            results = []
            for cmd in to_run:
                try:
                    self.log(f"RUNNING: {cmd}")
                    out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=30)
                    results.append((cmd, out.strip()[:1500]))
                    self.root.after(0, lambda c=cmd, o=out: self.append_chat("EXEC", f"$ {c}\n{o}"))
                except subprocess.CalledProcessError as e:
                    err = (e.output or str(e))[:800]
                    results.append((cmd, f"ERROR: {err}"))
                    self.root.after(0, lambda c=cmd, e=err: self.append_chat("EXEC ERROR", f"$ {c}\n{e}"))
                except Exception as e:
                    results.append((cmd, f"EXCEPTION: {e}"))
                    self.root.after(0, lambda c=cmd, e=e: self.append_chat("EXEC ERROR", f"$ {c}\n{e}"))
            self.root.after(0, lambda: self.log("Execution batch complete. Use 'Feed results back' to continue with JARVIS."))
            # Store last results for feeding back
            self.last_exec_results = results

        threading.Thread(target=runner, daemon=True).start()

    def feed_results_back(self):
        if not hasattr(self, "last_exec_results") or not self.last_exec_results:
            self.log("No recent execution results to feed back.", "WARN")
            return
        summary = "Execution results from my Kali machine:\n"
        for cmd, out in self.last_exec_results:
            summary += f"\nCommand: {cmd}\nOutput:\n{out}\n---\n"
        self.chat_history.append({"role": "user", "content": summary})
        self.append_chat("SYSTEM", "Fed execution results back to JARVIS as context.")
        self.log("Results fed back. You can now send a follow-up prompt like 'Continue the plan based on the results'.")

    def clear_pending(self):
        self.pending_commands = []
        self.refresh_cmd_list()

    def append_chat_history_for_model(self, role, content):
        self.chat_history.append({"role": role, "content": content})

# --- Main ---
if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisKaliUI(root)
    root.mainloop()
