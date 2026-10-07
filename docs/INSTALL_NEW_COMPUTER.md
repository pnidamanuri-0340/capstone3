# Moving FinLit to a New Computer: Install and Run Guide

This guide takes FinLit from the computer it was built on (the **old PC**) to another
computer (the **new PC**) and gets it running there.

---

## 1. What to copy (and what not to)

You only need **one file**: `dist\finlit.zip`, built in step 2. It is about 100 KB and contains:

| Included | What it is |
|---|---|
| `src\` | The application code, knowledge base and evaluation data |
| `scripts\` | Install, run and package scripts for Windows and macOS/Linux |
| `tests\` | Automated tests |
| `docs\`, `README.md`, `CLAUDE.md` | Documentation |
| `pyproject.toml` | The package definition and list of dependencies |
| `.env.example` | Settings template (no keys) |

**Do not copy** these. They are machine-specific or private, and the installer rebuilds them:

| Not copied | Why |
|---|---|
| `.venv\` | The Python environment only works on the computer that created it. The installer creates a new one (~1 GB) |
| `.env` | Contains your **API keys**. Never put it in a zip, email or shared drive. Re-enter the keys, or move the file separately (see step 4) |
| `data\` | Your local profiles, chat history and vector store. The installer rebuilds the vector store. Copy it only if you want to keep profiles and chats (step 2, option B) |
| `eval_results\`, `dist\`, `__pycache__\`, `*.egg-info\` | Generated files |

---

## 2. On the old PC: build the zip

Double-click **`scripts\package.bat`**, or run in the project folder:

```powershell
.venv\Scripts\python scripts\package.py
```

This creates `dist\finlit.zip`.

- **Option A (default), clean install:** the new PC starts with empty profiles and no chat history.
- **Option B, keep profiles and chats:** run `.venv\Scripts\python scripts\package.py --include-data`
  (or `scripts\package.bat --include-data`). This adds `data\` (saved profiles, holdings, conversations).

Copy `finlit.zip` to the new PC using a USB drive, OneDrive/Google Drive, or email to yourself.

---

## 3. On the new PC: prerequisites (one time)

| Requirement | How |
|---|---|
| Windows 10/11 (or macOS / Linux) | — |
| **Python 3.11, 3.12 or 3.13** (3.12 recommended) | Download from <https://www.python.org/downloads/>. In the installer, **tick "Add python.exe to PATH"**, then click *Install Now*. |
| Internet connection | Needed during install to download packages (~1 GB) and the embedding model (~80 MB). It's also needed while running, for the AI and market data. |
| Free disk space | About 2 GB |
| An AI API key | **OpenAI** (<https://platform.openai.com/api-keys>), or a free **Google Gemini** key (<https://aistudio.google.com/apikey>), or **Anthropic** (<https://console.anthropic.com/>) |
| (Optional) Alpha Vantage key | Free, for live stock data: <https://www.alphavantage.co/support/#api-key>. Without it, the app uses labelled sample data |

To check Python, open **Command Prompt** and type `py --version` or `python --version`. It should say 3.11 or newer.

---

## 4. On the new PC: install

1. **Unzip** `finlit.zip` to a simple location, for example `C:\finlit`. Right-click → *Extract All…*
   You should now have `C:\finlit\finlit\` containing `README.md`, `scripts\`, `src\` and so on.
   (Avoid OneDrive-synced folders for the install location. Syncing the large `.venv` folder is slow.)
2. **(Optional) bring your keys:** if you securely copied your old `.env`, put it in the same
   folder as `README.md` **before** installing. The installer keeps it and won't ask for keys.
3. **Run the installer:** open the `scripts` folder and **double-click `install.bat`**.
   - It finds Python, creates `.venv`, and installs all packages. The first install can take
     **10 to 30 minutes**, depending on the PC and internet speed. Long pauses with no output are normal.
   - If there is no `.env`, it asks for your keys. Paste your **OpenAI** key (right-click pastes in the
     console window) and press Enter. Press Enter to skip anything you don't have.
   - It builds the knowledge base and runs a **smoke test**. You should see `[PASS]` lines and
     `All checks passed.` A `[WARN]` for market data or a missing key is OK.
4. When you see **"Install complete"**, press any key to close the window.

Tested result (clean folder, from the zip): all 7 smoke checks `[PASS]`, including a live OpenAI
answer. The install took about 11 minutes on the original (slow) PC, with packages already cached.
Expect longer on a new PC that downloads everything.

> **Windows SmartScreen / antivirus:** if Windows warns about running a script, choose *More info → Run anyway*.
> The scripts only create files inside the FinLit folder.

---

## 5. Run the app

Double-click **`scripts\run.bat`**. A console window opens and your browser shows
**<http://localhost:8501>**. Keep the console window open while you use the app, and close it
(or press **Ctrl+C**) to stop the app.

Quick check in the app:
- The sidebar **Status** shows ✅ *AI: OpenAI (gpt-4o)* and ✅ *Knowledge base: 79 chunks*.
- Ask *"What is an index fund?"*. The answer shows the 📘 Financial Literacy badge and source citations.

**Using VS Code instead:** open the FinLit folder in VS Code (*File → Open Folder…*), pick
**"FinLit: Streamlit app"** in Run and Debug (Ctrl+Shift+D) and press **F5**. See *Running in VS Code* in the README.

**Desktop shortcut (optional):** right-click `scripts\run.bat` → *Send to → Desktop (create shortcut)*.

---

## 6. Changing keys or settings later

Open `.env` in the FinLit folder with Notepad, edit, save, and refresh the browser page. No restart is needed.

```ini
OPENAI_API_KEY=sk-...            # AI answers (used first if present)
GOOGLE_API_KEY=                  # optional alternative (free Gemini)
ALPHA_VANTAGE_API_KEY=           # optional live market data
FINLIT_PROVIDER=auto             # or: openai / google / anthropic
```

Put each key directly after `=`, with no quotes or spaces.

> **Windows environment variables win over `.env`.** If a key such as `OPENAI_API_KEY` is also set in
> *Windows Settings → System → About → Advanced system settings → Environment Variables*, that value is
> used and the `.env` line is ignored. On the original PC the OpenAI key is stored there, which is why the
> app worked without it in `.env`. **A new PC will not have it**, so put the key in `.env` (or enter it when
> the installer asks). To check from Command Prompt: `echo %OPENAI_API_KEY%`. If it prints the variable
> name unchanged, it's not set.

---

## 7. macOS / Linux

```bash
unzip finlit.zip && cd finlit
bash scripts/install.sh     # same steps as Windows: venv, packages, keys, knowledge base, smoke test
bash scripts/run.sh         # opens http://localhost:8501
```

If Python 3.11+ is missing: macOS uses `brew install python@3.12` or python.org. Ubuntu uses
`sudo apt install python3.12 python3.12-venv`.

---

## 8. Updating or removing

- **Update the code** from the old PC: build a new zip, extract it over the existing folder on the new PC
  (your `.env`, `.venv` and `data\` are not in the zip, so they are kept), then run `install.bat` again.
- **Uninstall:** delete the FinLit folder. Nothing is installed outside it.

---

## 9. Troubleshooting on a new PC

| Problem | Fix |
|---|---|
| `Python 3.11 or newer was not found` | Install Python from python.org with **"Add python.exe to PATH"** ticked, then open a **new** window and re-run `install.bat` |
| `install.bat` closes immediately | Open Command Prompt, `cd C:\finlit\finlit`, run `scripts\install.bat` to read the error |
| `pip install failed` / SSL or proxy errors | Check the internet connection. On a work or school network, a proxy may block downloads. Try another network |
| `running scripts is disabled on this system` | Use the `.bat` files, which bypass this for FinLit only |
| Sidebar shows ❌ AI or "No AI key is set" | Add `OPENAI_API_KEY=...` to `.env` in the FinLit folder, save, refresh the page |
| Edited the key in `.env` but the old one is still used | A Windows environment variable with the same name overrides `.env` (see section 6). Update or delete it there, then restart the app |
| "API key was rejected" / "no remaining credit" | Re-copy the full key. Check billing on the provider's website |
| Port 8501 already in use | `scripts\run.bat -Port 8502`, then open <http://localhost:8502> |
| "Knowledge base … is missing" | In the FinLit folder: `.venv\Scripts\finlit ingest` |
| Something is broken and you want to start over | Delete `.venv` and `data`, then run `install.bat` again |
| Check the installation at any time | `.venv\Scripts\finlit smoke` |
