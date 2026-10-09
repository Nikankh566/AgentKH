# Agent KH ✨ — Your Personal AI Desktop Agent

**Agent KH** is a free, open-source **AI desktop agent** in the style of
[Coucou](https://github.com/Louis-CFM/coucou): a tiny friend that lives at the
**top of your screen**. Click the island to chat, watch it work, and approve
its actions — no browser needed, everything happens in the island.

It **sees your screen** (vision), controls your **mouse and keyboard**, runs
**terminal commands**, manages **files**, connects to **MCP servers**, and
remembers you — powered by **Google Gemini** (or any OpenAI-compatible API).

English by default, فارسی هم پشتیبانی می‌شود 🇮🇷

## ✨ Features

- 🟣 **Island companion (Mochi)** — lives at the top of your screen; eyes follow your cursor, blinks, breathes, celebrates when done, turns orange when it needs approval
- 💬 **Chat in the island** — click to expand; streaming replies, click the model pill to switch models
- 📋 **Live activity feed** — watch every step: what it reads, runs and clicks
- ✅ **Approvals in the island** — Allow / Always allow / Deny with keyboard shortcuts (Y/N), Coucou-style
- 👁️ **Vision** — takes screenshots and actually *sees* buttons, windows and dialogs
- 🖱️ **Full mouse control** — move, click, double-click, scroll, drag
- ⌨️ **Full keyboard control** — type text (English/Persian), keys, hotkeys (e.g. Win+R)
- 🔌 **MCP support** — connect any [Model Context Protocol](https://modelcontextprotocol.io) server
- 🧠 **Long-term memory** — remembers facts about you across sessions (SQLite)
- 🎭 **Editable personality** — `soul.md`, editable from Settings
- 🌐 **Bilingual** — English default, one-tap switch to Persian
- 🖥️ **Drag Mochi out** — tear him off the island onto your desktop; double-click to send him home
- 🪟 **Windows installer** — `AgentKH-Setup.exe` installs, adds Start Menu shortcut and **auto-starts with Windows**

## 🚀 Install (Windows)

**Option A — installer (recommended):**
1. Download `AgentKH-Setup.exe` from the [Releases](../../releases) page
2. Run it — Agent KH installs to `%LOCALAPPDATA%\AgentKH` and starts with Windows automatically

**Option B — portable:**
1. Download `AgentKH-Windows.zip` from [Releases](../../releases), extract anywhere
2. Run `AgentKH.exe` — the island appears at the top of your screen

**Option C — from source (any OS with Python 3.9+ and tkinter):**
```bash
git clone https://github.com/Nikankh566/AgentKH.git
cd AgentKH
pip install pillow          # optional, enables vision (screenshots)
python agentkh.py
```
Add your Gemini API key in ⚙️ Settings
(get a free key at https://aistudio.google.com — no credit card).

## 🛠️ Build the .exe yourself

On Windows:
```bat
build.bat
```
This runs PyInstaller (`AgentKH.spec`) and produces `dist\AgentKH\AgentKH.exe`.
To build the setup wizard: `makensis installer.nsi`.
GitHub Actions builds both automatically on every `v*` tag (see `.github/workflows/build.yml`).

## ⚙️ Configuration

`config.json` (created on first run):

| Key | Description |
|---|---|
| `gemini_key` / `gemini_model` | Gemini API credentials |
| `provider` | `gemini` or `custom` (any OpenAI-compatible API) |
| `auto_approve` | Skip approval prompts (use carefully!) |
| `home_only` | Restrict file tools to the user folder |
| `mcp_servers` | MCP servers, e.g. `{"fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/docs"]}}` |
| `lang` | `en` (default) or `fa` |

## 🔒 Privacy & security

- Runs **locally** — only your prompts (and screenshots you ask it to take) go to the LLM API
- Your API key stays in your local `config.json`, never uploaded anywhere
- Approval prompts for every sensitive action; auto-approve is off by default

## 📁 Project layout

| File | What it is |
|---|---|
| `agentkh.py` | Island app: Mochi, chat/activity/settings views, approvals |
| `engine.py` | Agent core: LLM client, tools, agent loop |
| `mochi.py` | Mochi character (canvas animation) |
| `desktop.py` | Mouse/keyboard/screenshot control (pyautogui or Win32) |
| `mcp.py` | MCP stdio client |
| `soul.md` | Editable personality |
| `AgentKH.spec` / `build.bat` | PyInstaller build |
| `install.ps1` / `installer.nsi` | Windows installer |

## 🙏 Credits

Island UX inspired by [Coucou](https://github.com/Louis-CFM/coucou) by Louis Raillé (MIT).

## 📜 License

MIT — free for personal and commercial use. See [LICENSE](LICENSE).

---

<details>
<summary>🇮🇷 فارسی</summary>

**Agent KH** یه ایجنت هوش مصنوعی رایگان و متن‌بازه به سبک Coucou: یه دوست کوچیک که
**بالای صفحه** زندگی می‌کنه. روش کلیک کن تا چت باز بشه — بدون مرورگر، همه‌چیز توی
همون جزیره اتفاق می‌افته. صفحه رو می‌بینه، موس و کیبورد رو کنترل می‌کنه، دستور
ترمینال اجرا می‌کنه، به سرورهای MCP وصل می‌شه و تو رو یادش می‌مونه. با Gemini
(یا هر API سازگار با OpenAI) کار می‌کنه. برای نصب ویندوز، فایل `AgentKH-Setup.exe`
رو از صفحه Releases دانلود کن.
</details>
