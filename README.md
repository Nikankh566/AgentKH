# Agent KH ✨ — Your Personal AI Desktop Agent

**Agent KH** is a free, open-source **AI desktop agent** that lives on your own computer.
It sits at the **top of your screen** like a little companion, **sees your screen** (vision),
controls your **mouse and keyboard**, runs **terminal commands**, manages **files**,
connects to **MCP servers**, and remembers you — all powered by **Google Gemini**
(or any OpenAI-compatible API).

English by default, فارسی هم پشتیبانی می‌شود 🇮🇷

## ✨ Features

- 🟣 **Always-on-top companion** — draggable mascot on top of your screen; eyes follow your cursor, blinks, celebrates, turns orange when it needs your approval
- 👁️ **Vision** — takes screenshots and actually *sees* buttons, windows and dialogs
- 🖱️ **Full mouse control** — move, left/right/middle click, double-click, scroll, drag
- ⌨️ **Full keyboard control** — type text (English/Persian), press keys, hotkeys (e.g. Win+R)
- ✅ **Approval-first** — every mouse, keyboard, command or file-write action asks you first (Allow/Deny), right under the companion
- 🔌 **MCP support** — connect any [Model Context Protocol](https://modelcontextprotocol.io) server and use its tools directly
- 🧠 **Long-term memory** — remembers facts about you across sessions (SQLite)
- 🎭 **Editable personality** — `soul.md`, editable from the Settings panel
- 🌐 **Bilingual UI** — English default, one-tap switch to Persian (فارسی)
- 🪟 **Windows installer** — `AgentKH-Setup.exe` installs, adds Start Menu shortcut and **auto-starts with Windows**

## 🚀 Install (Windows)

**Option A — installer (recommended):**
1. Download `AgentKH-Setup.exe` from the [Releases](../../releases) page
2. Run it — Agent KH installs to `%LOCALAPPDATA%\AgentKH` and starts with Windows automatically

**Option B — portable:**
1. Download `AgentKH-Windows.zip` from [Releases](../../releases), extract anywhere
2. Run `AgentKH.exe` — chat opens at http://127.0.0.1:8765

**Option C — from source (any OS with Python 3.9+):**
```bash
git clone https://github.com/Nikankh566/AgentKH.git
cd AgentKH
pip install pillow          # optional, enables vision (screenshots)
python agentkh.py           # needs tkinter for the overlay companion
```
Then open http://127.0.0.1:8765 and enter your Gemini API key in ⚙️ Settings
(get a free key at https://aistudio.google.com — no credit card).

## 🛠️ Build the .exe yourself

On Windows:
```bat
build.bat
```
This runs PyInstaller (`AgentKH.spec`) and produces `dist\AgentKH\` with
`AgentKH.exe` (server) + `AgentKH-Companion.exe` (overlay).
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

## 🧠 How it works

```
You  →  web chat (EN/FA)  →  Agent KH server (tool loop)
                                ├─ Gemini / OpenAI-compatible LLM
                                ├─ desktop tools (mouse, keyboard, vision)
                                ├─ MCP server tools
                                └─ SQLite memory
       🟣 always-on-top companion (approval popups)
```

## 🔒 Privacy & security

- Runs **100% locally** — only your prompts (and screenshots you ask it to take) go to the LLM API
- Your API key stays in your local `config.json`, never uploaded anywhere
- Approval prompts for every sensitive action; auto-approve is off by default

## 📁 Project layout

| File | What it is |
|---|---|
| `agentkh.py` | Agent server + tool loop + web UI backend |
| `companion.py` | Always-on-top desktop companion (tkinter) |
| `desktop.py` | Mouse/keyboard/screenshot control (pyautogui or Win32) |
| `mcp.py` | MCP stdio client |
| `web/` | Chat UI (bilingual) |
| `soul.md` | Editable personality |
| `AgentKH.spec` / `build.bat` | PyInstaller build |
| `install.ps1` / `installer.nsi` | Windows installer |

## 📜 License

MIT — free for personal and commercial use. See [LICENSE](LICENSE).

---

<details>
<summary>🇮🇷 فارسی</summary>

**Agent KH** یه ایجنت هوش مصنوعی رایگان و متن‌بازه که روی کامپیوتر خودت اجرا می‌شه:
بالای صفحه می‌شینه، صفحه رو می‌بینه، موس و کیبورد رو کنترل می‌کنه، دستور ترمینال
اجرا می‌کنه، به سرورهای MCP وصل می‌شه و تو رو یادش می‌مونه. با Gemini (یا هر API
سازگار با OpenAI) کار می‌کنه. رابط کاربری انگلیسیه و با یه دکمه فارسی می‌شه.
برای نصب ویندوز، فایل `AgentKH-Setup.exe` رو از صفحه Releases دانلود کن.
</details>
