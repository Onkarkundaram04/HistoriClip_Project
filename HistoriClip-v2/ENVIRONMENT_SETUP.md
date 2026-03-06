# HistoriClip — Complete Environment Setup Guide

> **Supported Platforms:** Windows 10/11, Ubuntu 20.04+/Debian 12+, macOS 13+ (Apple Silicon & Intel)

---

## Table of Contents

1. [System Prerequisites](#-1-system-prerequisites)
2. [Clone & Configure API Keys](#-2-clone--configure-api-keys)
3. [Python AI Environment (Conda)](#-3-python-ai-environment-conda)
4. [Download the SDXL Lightning Model](#-4-download-the-sdxl-lightning-model-manual-step)
5. [Node.js Backend Setup](#-5-nodejs-backend-setup)
6. [React Frontend Setup](#-6-react-frontend-setup)
7. [MySQL Database Setup](#-7-mysql-database-setup)
8. [First Run & Auto-Downloaded Models](#-8-first-run--auto-downloaded-models)
9. [Starting the Application](#-9-starting-the-application)
10. [Troubleshooting](#-10-troubleshooting)

---

## ⚠️ 1. System Prerequisites

Install **ALL** of these before proceeding. If you skip even one, something **will** break.

### A. Anaconda or Miniconda (Required — Python environment manager)

The Python AI service runs inside a **Conda environment**. You cannot use raw pip with system Python — it will cause version clashes.

- **Download:** [Miniconda (recommended, lightweight)](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda (full)](https://docs.anaconda.com/anaconda/install/)

**Platform-specific install:**

| Platform | Install Method |
|---|---|
| **Windows** | Run the `.exe` installer. Check **"Add to PATH"** when prompted. |
| **Linux** | `bash Miniconda3-latest-Linux-x86_64.sh` — answer **yes** to initialize conda. |
| **macOS** | `bash Miniconda3-latest-MacOSX-arm64.sh` (Apple Silicon) or `Miniconda3-latest-MacOSX-x86_64.sh` (Intel). Answer **yes** to initialize. |

- **Verify installation** — open a **new** terminal and run:
  ```bash
  conda --version
  ```
  You should see something like `conda 24.x.x`. If you get `"conda is not recognized"` / `"command not found"`, restart your terminal or add conda to PATH manually.

### B. NVIDIA GPU + Driver (Required — AI inference needs CUDA)

An NVIDIA GPU with **CUDA-capable driver** is mandatory. All AI models (DINOv2, SDXL Lightning) run on GPU.

| Platform | How to Install |
|---|---|
| **Windows** | Download from [NVIDIA Driver Downloads](https://www.nvidia.com/download/index.aspx). Run the `.exe` installer. |
| **Linux (Ubuntu/Debian)** | `sudo apt update && sudo apt install -y nvidia-driver-535` (or latest version). Reboot after install. |
| **macOS** | ⚠️ **macOS does NOT support CUDA.** NVIDIA GPUs are not available on modern Macs. You would need to modify the code to use MPS (Apple Metal) or CPU-only mode. This is **not officially supported** — use a Linux/Windows machine for full functionality. |

- **Verify installation** — open a terminal and run:
  ```bash
  nvidia-smi
  ```
  You should see your GPU name, driver version, and **CUDA Version ≥ 12.1**. If you don't see this, update your driver.

### C. Node.js v18 LTS or v20 LTS (Required — backend server)

| Platform | How to Install |
|---|---|
| **Windows** | Download the `.msi` installer from [Node.js Official](https://nodejs.org/) — pick the **LTS** version. |
| **Linux** | Use NodeSource: `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash - && sudo apt install -y nodejs` |
| **macOS** | `brew install node@20` (requires [Homebrew](https://brew.sh/)) or download from [Node.js Official](https://nodejs.org/). |

- **Verify installation:**
  ```bash
  node --version
  npm --version
  ```
  > ⚠️ **Do NOT use Node.js 14 or 16** — the backend uses `express-rate-limit` v7 and other packages that require ES2020+ syntax. You'll get cryptic syntax errors.

### D. MySQL Server (Required — user data, video history)

| Platform | How to Install |
|---|---|
| **Windows** | Download [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) or install via [XAMPP](https://www.apachefriends.org/index.html). |
| **Linux (Ubuntu/Debian)** | `sudo apt update && sudo apt install -y mysql-server` then `sudo mysql_secure_installation` to set root password. |
| **macOS** | `brew install mysql` then `brew services start mysql` and `mysql_secure_installation` to set root password. |

- Make sure the MySQL service is **running** before launching HistoriClip.
- Remember your **root password** — you'll need it for the `.env` file.

### E. FFmpeg (Required — video assembly)

The Python video editor module calls FFmpeg directly to stitch images + audio into the final documentary video. Without it, video generation **will crash** with `OSError: [Errno 2] No such file or directory`.

| Platform | How to Install |
|---|---|
| **Windows** | 1. Download from [FFmpeg for Windows](https://www.gyan.dev/ffmpeg/builds/) — the **"essentials"** build. <br> 2. Extract ZIP to `C:\ffmpeg` (so you have `C:\ffmpeg\bin\ffmpeg.exe`). <br> 3. Add `C:\ffmpeg\bin` to your System PATH: Search "Environment Variables" → System variables → `Path` → Edit → New → `C:\ffmpeg\bin`. |
| **Linux (Ubuntu/Debian)** | `sudo apt update && sudo apt install -y ffmpeg` |
| **macOS** | `brew install ffmpeg` |

- **Verify installation** — open a **new** terminal and run:
  ```bash
  ffmpeg -version
  ```
  You should see `ffmpeg version N-xxxxx` (or similar).

### F. Git (Required — for cloning the repository)

| Platform | How to Install |
|---|---|
| **Windows** | Download from [Git for Windows](https://git-scm.com/download/win). |
| **Linux** | `sudo apt install -y git` |
| **macOS** | `brew install git` or install Xcode Command Line Tools: `xcode-select --install` |

- **Verify:** `git --version`

---

## 🔑 2. Clone & Configure API Keys

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/HistoriClip.git
cd HistoriClip
```

### Step 2: Create the `.env` file

The project requires API keys for Google Gemini, Google Vision, and Mapillary. These are stored in a **single `.env` file** in the root of `HistoriClip/`.

```bash
cp .env.example .env
```

> On Windows CMD (if `cp` doesn't work):
> ```cmd
> copy .env.example .env
> ```

### Step 3: Fill in your actual API keys

Open the `.env` file in any text editor and fill in these values:

| Variable | Where to Get It | Required? |
|---|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) — create a free API key | ✅ Yes |
| `GOOGLE_VISION_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/) — enable Vision API, create credentials | ✅ Yes |
| `MAPILLARY_CLIENT_TOKEN` | [Mapillary Developer Portal](https://www.mapillary.com/developer) — register an app | ✅ Yes (for data collection) |
| `DB_PASSWORD` | Your local MySQL root password | ✅ Yes |
| `JWT_SECRET` | Any strong random string (change from default) | ✅ Yes (for production) |

All other values in `.env` have sensible defaults and **do not need to be changed** for local development.

> ⚠️ **NEVER commit the `.env` file to GitHub.** The `.gitignore` already blocks it, but double-check.

---

## 🐍 3. Python AI Environment (Conda)

> **This is the step where most people face issues.** Follow it exactly.

Setting up the AI environment is tricky because PyTorch, CUDA, NumPy, and bitsandbytes all have very specific version requirements. We have **frozen the exact working environment** so you never need to debug dependency conflicts.

### Option 1: Conda Environment from YAML (Recommended — one command)

This is the fastest and most reliable method. The `exact_environment.yml` file contains **every single package** with exact versions that are guaranteed to work together.

1. **Open a terminal:**
   - **Windows:** Open **Anaconda Prompt** (search in Start Menu — **NOT** regular CMD or PowerShell).
   - **Linux/macOS:** Open any terminal (conda should already be on your PATH).

2. Navigate to the Python AI service folder:
   ```bash
   cd path/to/HistoriClip/python-ai-service
   ```

3. Create the environment:
   ```bash
   conda env create -f exact_environment.yml
   ```
   > This will take 5-15 minutes. It installs Python 3.11.14, PyTorch 2.5.1, CUDA toolkit 12.1, and all pip packages.

   > ⚠️ **Linux/macOS users:** The `exact_environment.yml` was exported on Windows. If package resolution fails, use **Option 2** (manual install) instead — it works on all platforms.

4. Activate the environment:
   ```bash
   conda activate historiclip
   ```

5. **Verify everything installed correctly:**
   ```bash
   python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')"
   ```
   Expected output: `PyTorch 2.5.1, CUDA available: True`

   > ❌ If CUDA shows `False`, your NVIDIA driver may be outdated. Go back to Step 1B.

### Option 2: Step-by-Step Manual Install (If YAML fails or you're on Linux/macOS)

If the YAML method fails (common on Linux/macOS since the YAML was exported on Windows) or you want to understand each dependency:

1. **Create the base Conda environment with the exact Python version:**
   ```bash
   conda create -n historiclip python=3.11.14 -y
   conda activate historiclip
   ```

2. **Install PyTorch with CUDA 12.1** (this MUST be done via conda, NOT pip):
   ```bash
   conda install pytorch==2.5.1 torchvision==0.20.1 pytorch-cuda=12.1 -c pytorch -c nvidia -y
   ```

3. **Install CUDA toolkit** (needed for GPU kernels):
   ```bash
   conda install -c nvidia cuda-toolkit=12.1.0 -y
   ```

4. **Install all remaining pip packages** using the frozen requirements:
   ```bash
   cd path/to/HistoriClip/python-ai-service
   pip install -r exact_requirements.txt
   ```

   > ⚠️ **Linux/macOS note on `bitsandbytes`:** The `exact_requirements.txt` includes a Windows-specific wheel for `bitsandbytes`. On Linux, install it normally instead:
   > ```bash
   > pip install bitsandbytes==0.41.1
   > ```
   > On **macOS**, bitsandbytes is not needed (no CUDA). You can skip it or install the CPU-only version.

5. **Verify:**
   ```bash
   python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')"
   ```

> **Why Python 3.11.14 specifically?** Python 3.12 breaks several packages (bitsandbytes, some torch operations). Python 3.10 or older lacks features needed by newer transformers. Python 3.11.14 is the sweet spot.

> **Why not xformers?** On Windows, installing xformers requires a C++ compiler and frequently fails. On Linux it works but is optional. PyTorch 2.5.1 includes native SDPA (Scaled Dot Product Attention) which provides equivalent acceleration out of the box on all platforms.

### Which Requirements File Does What?

| File | Purpose | When to Use |
|---|---|---|
| `exact_environment.yml` | Complete Conda environment with every package and exact versions | **Use this first** — one command to set up everything (best on Windows) |
| `exact_requirements.txt` | Frozen pip packages only (requires PyTorch installed via conda first) | Use with Option 2, or if `exact_environment.yml` fails (recommended for Linux/macOS) |
| `requirements.txt` | Flexible/minimum versions for reference — shows what each package is for | **Do NOT install this directly** — it's documentation. Use the exact files above instead |

---

## 📥 4. Download the SDXL Lightning Model (Manual Step)

The project uses **SDXL Lightning 8-Step** by ByteDance for AI image generation. This model file is **~6.5 GB** and too large for GitHub, so you must download it manually.

### Exact Model Required

| Property | Value |
|---|---|
| **Model Name** | SDXL Lightning 8-Step |
| **Filename** | `sdxlLightning_8Steps.safetensors` |
| **File Size** | ~6.46 GB |
| **Format** | SafeTensors (`.safetensors`) |
| **Creator** | ByteDance |

### Download Link

**Download from CivitAI:**
[https://civitai.com/models/424149/sdxl-lightning](https://civitai.com/models/424149/sdxl-lightning)

> Look for the **8-Step** variant. Download the `.safetensors` file (NOT the LoRA, NOT the 4-Step or 2-Step variant).

**Alternative — Download from HuggingFace:**
[https://huggingface.co/ByteDance/SDXL-Lightning](https://huggingface.co/ByteDance/SDXL-Lightning)

> Download the file named `sdxl_lightning_8step.safetensors` and **rename it** to `sdxlLightning_8Steps.safetensors`.

### Where to Place It

After downloading, place the file at this **exact path**:

```
HistoriClip/
└── python-ai-service/
    └── models/
        └── sdxlLightning_8Steps.safetensors   ← place it here
```

If the `models/` folder doesn't exist, create it:

```bash
# Windows
mkdir python-ai-service\models

# Linux / macOS
mkdir -p python-ai-service/models
```

> ⚠️ **The filename must be exactly `sdxlLightning_8Steps.safetensors`** — the code loads it by this exact name. If the downloaded file has a different name, rename it.

### Verify

The file should be approximately **6.4-6.5 GB**. If it's much smaller, the download may have been corrupted — re-download it.

---

## 📦 5. Node.js Backend Setup

1. **Open a terminal.**
2. Navigate to the backend directory:
   ```bash
   cd path/to/HistoriClip/backend
   ```
3. Install the dependencies:
   ```bash
   npm install
   ```
   This creates a `node_modules/` folder and downloads Express, MySQL2, JWT, etc.

---

## ⚛️ 6. React Frontend Setup

1. **Open a terminal.**
2. Navigate to the frontend-react directory:
   ```bash
   cd path/to/HistoriClip/frontend-react
   ```
3. Install the dependencies:
   ```bash
   npm install
   ```
   This installs React, Vite, React Router, and other frontend packages.

---

## 🗄️ 7. MySQL Database Setup

**If you skip this, the backend will crash on startup with `"Database connection failed"`.**

1. **Make sure MySQL server is running.**

   | Platform | How to Check / Start |
   |---|---|
   | **Windows (XAMPP)** | Open XAMPP Control Panel → click **Start** next to MySQL. |
   | **Windows (standalone)** | Open **Services** (search in Start Menu) → find `MySQL` → ensure status is **Running**. |
   | **Linux** | `sudo systemctl start mysql` then `sudo systemctl status mysql` |
   | **macOS (Homebrew)** | `brew services start mysql` then `brew services list` |

2. **Create the database.** Open MySQL Workbench, terminal MySQL client, or any MySQL GUI and run:
   ```sql
   CREATE DATABASE historiclip;
   USE historiclip;
   ```

   > **Linux/macOS terminal access:**
   > ```bash
   > sudo mysql -u root -p
   > ```

3. **Import the database schema (tables).** Run the provided SQL file:
   - **Option A — MySQL Workbench:** Open `backend/src/database/schema.sql` and execute it.
   - **Option B — Command line (all platforms):**
     ```bash
     mysql -u root -p historiclip < backend/src/database/schema.sql
     ```
     Enter your MySQL root password when prompted.

4. **Update the `.env` file** with your MySQL password (if not already done in Step 2):
   ```
   DB_PASSWORD=your_mysql_root_password
   ```

---

## 🤖 8. First Run & Auto-Downloaded Models

The **very first time** you start the Python AI Service, it will automatically download several AI models from HuggingFace. This is **normal and expected**.

| Model | HuggingFace ID | Size | Used For |
|---|---|---|---|
| DINOv2 | `facebook/dinov2-base` | ~350 MB | Visual place recognition (Location Engine) |
| TinyVAE | `madebyollin/taesdxl` | ~40 MB | Fast image decoding for SDXL |
| DISK + LightGlue | via Kornia library | ~100 MB | Geometric verification (XAI keypoint matching) |

**What you need:**
- Active internet connection
- ~500 MB of free disk space (for auto-downloaded models)
- 5-15 minutes of patience (first time only)

After the first successful run, these models are **cached locally** and all subsequent startups will be fast.

> 📝 **Note:** The SDXL Lightning model (~6.5 GB) is **NOT auto-downloaded** — you must download it manually as described in Step 4 above.

---

## 🚀 9. Starting the Application

Once everything is set up (MySQL running, `.env` configured, Conda environment ready, SDXL model downloaded, npm packages installed):

### Quick Start — Windows

Simply **double-click `windows_start.bat`** in the `HistoriClip/` root folder.

This automatically opens **3 terminal windows**:

| Service | URL | What It Does |
|---|---|---|
| Node.js Backend | `http://localhost:5000` | REST API, user auth, database |
| Python AI Service | `http://localhost:5001` | Image analysis, location engine, video generation |
| React Frontend (Vite) | `http://localhost:5173` | The web UI you interact with |

The browser will automatically open `http://localhost:5173` after ~5 seconds.

### Quick Start — Linux / macOS

1. **Open a terminal** in the `HistoriClip/` root folder.
2. **Make the scripts executable** (first time only):
   ```bash
   chmod +x start.sh stop.sh
   ```
3. **Run the start script:**
   ```bash
   ./start.sh
   ```

This automatically starts all 3 services in the background and writes their output to log files (`backend.log`, `ai_service.log`, `frontend.log`).

The browser will automatically open `http://localhost:5173` after a few seconds.

### Stopping the Application

| Platform | How to Stop |
|---|---|
| **Windows** | Double-click `windows_stop.bat` — force-kills all 3 services and frees ports 5000, 5001, 5173. |
| **Linux/macOS** | Run `./stop.sh` in the terminal. This cleanly detects and terminates the processes running on ports 5000, 5001, and 5173. |

---

## 🛠️ 10. Troubleshooting

### Common Errors & Fixes

| # | Error Message | Cause | Fix |
|---|---|---|---|
| 1 | `❌ Database connection failed` | MySQL not running or wrong password | Start MySQL service. Check `DB_PASSWORD` in `.env` matches your actual MySQL root password. |
| 2 | `Table 'historiclip.users' doesn't exist` | Database schema not imported | Run `schema.sql` in MySQL Workbench or CLI (see Step 7). |
| 3 | `CUDA not available` / `torch.cuda.is_available()` returns `False` | Wrong PyTorch build or outdated NVIDIA driver | Update NVIDIA driver (Step 1B). Reinstall environment via `exact_environment.yml` (Step 3). |
| 4 | `OSError: [Errno 2] No such file or directory` during video generation | FFmpeg not installed or not in system PATH | **Windows:** Install FFmpeg and add `C:\ffmpeg\bin` to PATH (Step 1E). **Linux:** `sudo apt install ffmpeg`. **macOS:** `brew install ffmpeg`. Open a **new** terminal after installing. |
| 5 | `ModuleNotFoundError: No module named 'xxx'` | Wrong Python environment is active | Run `conda activate historiclip` before starting the AI service. |
| 6 | `FileNotFoundError: .../models/sdxlLightning_8Steps.safetensors` | SDXL model not downloaded | Download it manually (Step 4) and place in `python-ai-service/models/`. |
| 7 | `bitsandbytes` install fails | Platform-specific issue | **Windows:** The `exact_requirements.txt` uses a Windows wheel. **Linux:** `pip install bitsandbytes==0.41.1` (works natively). **macOS:** Skip it (no CUDA support). |
| 8 | Slow first startup (5-15 minutes) | AI models downloading from HuggingFace for the first time | This is normal — see Step 8. |
| 9 | `conda: command not found` / `conda is not recognized` | Conda not in PATH | **Windows:** Restart terminal or use Anaconda Prompt. **Linux/macOS:** Run `source ~/miniconda3/etc/profile.d/conda.sh` or restart your shell. |
| 10 | `SyntaxError` or `Unexpected token` in Node.js | Using Node.js version < 18 | Install Node.js 18 LTS or 20 LTS (Step 1C). |
| 11 | Port already in use (5000, 5001, or 5173) | Another process on that port | **Windows:** Run `windows_stop.bat`. **Linux/macOS:** `lsof -ti:5000 \| xargs kill -9` |
| 12 | `npm install` fails with permission errors | Missing permissions | **Windows:** Run terminal as Administrator. **Linux/macOS:** Do NOT use `sudo npm install` — fix npm permissions instead: `sudo chown -R $(whoami) ~/.npm` |
| 13 | `exact_environment.yml` fails on Linux/macOS | YAML was exported on Windows, contains Windows-only packages | Use **Option 2** (manual install) in Step 3 instead. |

### Still Stuck?

1. Make sure **every** prerequisite from Step 1 is installed and verified.
2. Make sure you're using the **Conda environment** (`conda activate historiclip`), not system Python.
3. Make sure the `.env` file exists and has valid API keys.
4. Make sure MySQL is **running** (not just installed).
5. Make sure the SDXL model file is at `python-ai-service/models/sdxlLightning_8Steps.safetensors`.
6. **macOS users:** Full CUDA/GPU support requires an NVIDIA GPU which modern Macs don't have. The project is designed for Windows/Linux with NVIDIA GPUs.
