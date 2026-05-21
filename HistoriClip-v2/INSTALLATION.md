# HistoriClip — Complete Installation & Setup Guide

> **Supported Platforms:** Windows 10/11, Ubuntu 20.04+/Debian 12+, macOS 13+ (Apple Silicon & Intel)

This guide walks you through setting up and running the entire HistoriClip ecosystem. Follow the steps in sequence to ensure all services connect correctly.

---

## 📋 Table of Contents

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

Install **all** of the following tools before proceeding. Skipping dependencies will cause generation or runtime failures.

### A. Anaconda or Miniconda
The Python AI service runs inside a **Conda environment**. Raw system Python installation is not supported due to complex ML dependency version constraints.
*   **Download:** [Miniconda (recommended, lightweight)](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda (full suite)](https://docs.anaconda.com/anaconda/install/)
*   **Verify installation:** Open a new terminal and run:
    ```bash
    conda --version
    ```

### B. NVIDIA GPU & Drivers (Highly Recommended)
An NVIDIA GPU with a CUDA-capable driver is required to run the local diffusion (SDXL Lightning) and visual feature extraction (DINOv2) models efficiently.
*   **Drivers:** Download and install drivers from [NVIDIA Driver Downloads](https://www.nvidia.com/download/index.aspx).
*   **Verify CUDA Support:** Run:
    ```bash
    nvidia-smi
    ```
    Ensure the reported **CUDA Version is 12.1** or higher.
*   *Note for macOS users:* Modern macOS devices do not support NVIDIA CUDA. You will need to run the service in CPU-only mode, which is significantly slower and requires manual code adjustments.

### C. Node.js (v18 or v20 LTS)
The backend REST server uses modern ES2020 features and rate limiters requiring Node.js 18+.
*   **Download:** Install the LTS version from [Node.js Official](https://nodejs.org/).
*   **Verify:**
    ```bash
    node --version
    ```

### D. MySQL Server (v8.x)
Used to persist user accounts, authentication records, and generated video history.
*   **Download:** [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) or run via local bundles like XAMPP.
*   Ensure the MySQL service is running and note your root password.

### E. FFmpeg
The video assembler programmatically stitches synthesized audio and generated images together. FFmpeg must be added to your system's PATH.
*   **Windows Installation:**
    1. Download the "essentials" build from [FFmpeg for Windows](https://www.gyan.dev/ffmpeg/builds/).
    2. Extract the archive to `C:\ffmpeg`.
    3. Add `C:\ffmpeg\bin` to your System Environment variables under the `Path` variable.
*   **Linux Installation:**
    ```bash
    sudo apt update && sudo apt install -y ffmpeg
    ```
*   **macOS Installation:**
    ```bash
    brew install ffmpeg
    ```
*   **Verify:** Run `ffmpeg -version` in a new terminal window.

---

## 🔑 2. Clone & Configure API Keys

### Step 1: Clone the Project
```bash
git clone https://github.com/YOUR_USERNAME/HistoriClip.git
cd HistoriClip
```

### Step 2: Create the `.env` File
Copy the example file to create your active configuration in the root directory:
```bash
# Windows Command Prompt
copy .env.example .env

# Bash (Linux/macOS)
cp .env.example .env
```

### Step 3: Populate API Keys
Open `.env` in a text editor and fill in the following variables:
*   `GEMINI_API_KEY`: Get a free key from the [Google AI Studio Console](https://aistudio.google.com/app/apikey).
*   `GOOGLE_VISION_API_KEY`: Enable the Vision API and create credentials in the [Google Cloud Console](https://console.cloud.google.com/).
*   `MAPILLARY_CLIENT_TOKEN`: Register an application in the [Mapillary Developer Portal](https://www.mapillary.com/developer).
*   `DB_PASSWORD`: Your local MySQL root password.
*   `JWT_SECRET`: A secure, randomized string for signing session tokens.

---

## 🐍 3. Python AI Environment (Conda)

Setting up the ML dependencies requires precise version alignment between PyTorch, CUDA Toolkit, and helper packages.

### Option 1: Automatic Environment Build (Recommended)
This uses the frozen conda environment blueprint to build everything in one step.
1. Open the **Anaconda Prompt** (Windows) or a standard terminal (Linux).
2. Navigate to the service folder:
   ```bash
   cd python-ai-service
   ```
3. Create the environment from the YAML blueprint:
   ```bash
   conda env create -f exact_environment.yml
   ```
4. Activate the environment:
   ```bash
   conda activate historiclip
   ```

### Option 2: Step-by-Step Manual Install (Linux/macOS fallback)
If package resolution fails during YAML import (common on non-Windows platforms):
1. Create a Python 3.11 environment:
   ```bash
   conda create -n historiclip python=3.11.14 -y
   conda activate historiclip
   ```
2. Install PyTorch compiled for CUDA 12.1:
   ```bash
   conda install pytorch==2.5.1 torchvision==0.20.1 pytorch-cuda=12.1 -c pytorch -c nvidia -y
   ```
3. Install the CUDA toolkit:
   ```bash
   conda install -c nvidia cuda-toolkit=12.1.0 -y
   ```
4. Install pip dependencies:
   ```bash
   pip install -r exact_requirements.txt
   ```
   *Note for Linux/macOS:* On Linux, replace the bitsandbytes line with `pip install bitsandbytes==0.41.1`. On macOS, skip bitsandbytes.

5. **Verify GPU acceleration is enabled:**
   ```bash
   python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA available: {torch.cuda.is_available()}')"
   ```
   Ensure it prints `CUDA available: True`.

---

## 📥 4. Download the SDXL Lightning Model

HistoriClip uses **Stable Diffusion XL (SDXL) Lightning 8-Step** by ByteDance for rendering visual frames. The weights file is large (~6.46 GB) and must be placed manually.

1. **Download:** Get the 8-step SafeTensors model (`sdxl_lightning_8step.safetensors`) from [HuggingFace Hub](https://huggingface.co/ByteDance/SDXL-Lightning) or [CivitAI](https://civitai.com/models/424149/sdxl-lightning).
2. **Rename:** Rename the downloaded file to exactly: `sdxlLightning_8Steps.safetensors`.
3. **Move:** Place the file inside the models directory:
   ```
   HistoriClip/
   └── python-ai-service/
       └── models/
           └── sdxlLightning_8Steps.safetensors
   ```
   Create the `models` directory if it does not exist.

---

## 📦 5. Node.js Backend Setup

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```

---

## ⚛️ 6. React Frontend Setup

1. Navigate to the React frontend directory:
   ```bash
   cd frontend-react
   ```
2. Install UI dependencies:
   ```bash
   npm install
   ```

---

## 🗄️ 7. MySQL Database Setup

1. Make sure your MySQL service is running.
2. Log into your database server and initialize the schema:
   ```sql
   CREATE DATABASE historiclip;
   ```
3. Import the database tables from the schema file:
   ```bash
   # From the root directory of the project
   mysql -u root -p historiclip < backend/src/database/schema.sql
   ```
   Alternatively, open `backend/src/database/schema.sql` in MySQL Workbench and run it.

---

## 🤖 8. First Run & Auto-Downloaded Models

The first time you process an image, the Python service will download auxiliary models from HuggingFace to coordinate the VPR and XAI stages. This is normal and requires a stable internet connection.

| Model | HuggingFace Repository | Size | Core Usage |
| :--- | :--- | :--- | :--- |
| **DINOv2** | `facebook/dinov2-base` | ~350 MB | Visual Place Recognition (VPR) features |
| **TinyVAE** | `madebyollin/taesdxl` | ~40 MB | High-speed SDXL image decoder |
| **LightGlue** | Loaded via Kornia | ~100 MB | Keypoint verification and matching |

---

## 🚀 9. Starting the Application

### Windows Startup
Run the unified startup batch file in the root folder:
```cmd
windows_start.bat
```
This launches three separate cmd windows:
*   **React Frontend:** `http://localhost:5173`
*   **Express Backend API:** `http://localhost:5000`
*   **Python AI Service:** `http://localhost:5001`

To stop all services, run:
```cmd
windows_stop.bat
```

### Linux & macOS Startup
1. Grant execute permissions to the scripts:
   ```bash
   chmod +x start.sh stop.sh
   ```
2. Execute the start script:
   ```bash
   ./start.sh
   ```
This starts the processes in the background, redirecting output logs to `backend.log`, `ai_service.log`, and `frontend.log` in the root folder.

To stop the background services, execute:
```bash
./stop.sh
```

---

## 🛠️ 10. Troubleshooting

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| `❌ Database connection failed` | MySQL service offline / bad password | Start MySQL service. Double-check `DB_PASSWORD` in `.env`. |
| `Table 'historiclip.users' doesn't exist` | Database tables not imported | Import the schema sql file using step 7. |
| `CUDA available: False` | Outdated GPU drivers or wrong PyTorch build | Update drivers from NVIDIA. Rebuild Conda environment from YAML. |
| `OSError: [Errno 2] No such file or directory` | FFmpeg missing from PATH | Verify FFmpeg installation and check system PATH. Restart your terminal. |
| `FileNotFoundError: sdxlLightning_8Steps.safetensors` | Model weights missing or named incorrectly | Download weights and place them in `python-ai-service/models/` with correct name. |
| `conda: command not found` | Anaconda/Miniconda not added to terminal PATH | Open Anaconda Prompt directly or run initialization scripts. |
| Port in use conflicts | Ghost processes still binding ports | Run `windows_stop.bat` (Windows) or `./stop.sh` (Linux/macOS) to free ports. |
