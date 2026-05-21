<div align="center">

# 🎞️ HistoriClip

**An AI-Powered Historical Documentary Video Generator from Street-Level Imagery**

[![Node.js](https://img.shields.io/badge/Node.js-18.x%20%7C%2020.x-339933?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![React](https://img.shields.io/badge/React-19.x-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.5.1-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.x-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://www.mysql.com/)

[Features](#-key-features) • [Architecture](#-system-architecture) • [Tech Stack](#-tech-stack) • [Installation](#-getting-started) • [Team](#-team)

</div>

---

## 📖 Overview

**HistoriClip** is a full-stack AI platform designed to dynamically generate rich, historical documentary-style videos based purely on street-level user imagery. 

By simply uploading an image of a historical landmark, HistoriClip automatically identifies the location, verifies the architectural geometry, fetches relevant historical context, and generates a compelling, fully narrated documentary video complete with historically accurate, stylized AI images and Ken Burns visual effects.

This project was built to address the gap in automated, context-aware multimedia generation for heritage sites, making history accessible, visually spectacular, and highly engaging.

---

## ✨ Key Features

- **🌍 Visual Place Recognition:** Uses a fine-tuned pipeline (powered by Facebook's DINOv2 and FAISS) to accurately identify specific landmarks from thousands of reference locations under varying conditions.
- **🔍 Explainable AI (XAI):** Employs state-of-the-art keypoint matching (DISK + LightGlue) to geometrically verify the structural accuracy of the identified landmark, providing visual feature-matching proof to the user.
- **📜 Automated Storytelling:** Integrates with Google Gemini to dynamically script captivating documentary narratives complete with proper historical pacing, facts, and structure.
- **🎨 Visual Generation:** Employs SDXL Lightning (8-Step) to rapidly synthesize historically-themed imagery matching the narrative script.
- **🎬 Automated Video Assembly:** Programmatically pairs synthesized audio and AI-generated images, applying zooming "Ken Burns" effects and transitions to assemble a seamless documentary using FFmpeg.
- **💻 Modern Full-Stack UI:** A responsive, visually stunning web application built on React/Vite, offering video download, historical archives, and a rich user dashboard.

---

## 🏗 System Architecture

The project is structured as a distributed microservices platform consisting of three primary operational layers:

1. **Frontend (React + Vite):** The user-facing client providing the interface for photo uploading, video watching, history browsing, and XAI inspection.
2. **Backend Engine (Node.js + Express):** The RESTful API layer handling user authentication (JWT), database operations (MySQL), file storage, rate limiting, and request routing.
3. **AI Microservice (Python / Flask):** The heavy-lifting engine executing all GPU-accelerated tasks including the DINOv2 Location Engine, Geometrical matching, LLM integration, Diffusion generation, and Video stitching.

---

## 🛠 Tech Stack

### AI & Machine Learning
*   **Computer Vision:** `PyTorch`, `Transformers` (HuggingFace), `Kornia` (DISK + LightGlue XAI), `OpenCV`
*   **Vector Search:** `FAISS`
*   **Image Generation:** `SDXL Lightning` (via `diffusers` / `bitsandbytes`)
*   **Language Models:** Google Gemini API
*   **Audio & Video:** `gTTS` (Text-to-Speech), `MoviePy`, `FFmpeg`

### Application Layer
*   **Frontend:** `React 19`, `Vite`, `TailwindCSS`, `Lucide React`
*   **Backend:** `Node.js`, `Express.js`, `Axios`, `Multer`, `Bcrypt.js`, `Winston`
*   **Database:** `MySQL`

---

## 🚀 Getting Started

Deploying the whole ecosystem properly requires specific system dependencies (Conda environments, NVIDIA CUDA toolkits, exact Python/Node versions, etc.) to prevent version clashes. 

We have prepared a **bulletproof, comprehensive step-by-step guide** for configuring the project on Windows, Linux, and macOS.

👉 **[Read the Complete Environment Setup Guide here](./ENVIRONMENT_SETUP.md)** 👈

### Quick Overview of Setup
1. Verify prerequisites (`Miniconda`, `CUDA 12.1`, `Node 18/20`, `MySQL`, `FFmpeg`).
2. Configure your API keys (`Gemini`, `Google Vision`, `Mapillary`) in a `.env` file.
3. Build the AI Conda environment using the exact frozen dependency YAML.
4. Download the heavy `SDXL Lightning` model weights manually.
5. Create the database schemas.
6. Run the platform using the provided `windows_start.bat` or `start.sh` scripts.

---

## 🎮 Usage

1. Launch all 3 services using `windows_start.bat` (Windows) or `./start.sh` (Linux/macOS).
2. Open your browser to `http://localhost:5173`.
3. Create an account or log in.
4. Upload an image of a historical landmark.
5. Wait as the system processes the image, generating the location data, XAI proof, and final video.
6. View your documentary on the Video Details page or revisit it later from your History dashboard!

---

## 👥 Team

This project was developed collaboratively as a Final Year University Project by:

*   **Onkar Kundaram** - Python AI Services and Model Integration
*   **Vishwas Kude** - Backend Services and Database Management
*   **Prajwal Khobragade** - Frontend Services and UI/UX Development

---

## 📄 License

This is a personal/academic team project. No external licensing is provided at this time. All rights reserved by the original project authors.
