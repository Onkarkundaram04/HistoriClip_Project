<p align="center">
	<img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=0:0F172A,50:1D4ED8,100:0EA5E9&text=HistoriClip&fontColor=FFFFFF&fontSize=64&fontAlignY=38&desc=Street%20Image%20to%20AI%20Historical%20Documentary&descAlignY=58&animation=fadeIn" alt="HistoriClip Banner" />
</p>

<p align="center">
	<a href="./HistoriClip-v2/INSTALLATION.md"><img src="https://img.shields.io/badge/Setup-Environment%20Guide-0F172A?style=flat-square&logo=readthedocs&logoColor=white" alt="Setup Guide" /></a>
	<a href="https://github.com/Onkarkundaram04/HistoriClip_Project/commits"><img src="https://img.shields.io/github/last-commit/Onkarkundaram04/HistoriClip_Project?style=flat-square&logo=github&logoColor=white&color=1E293B" alt="Last Commit" /></a>
	<img src="https://img.shields.io/github/repo-size/Onkarkundaram04/HistoriClip_Project?style=flat-square&logo=github&logoColor=white&color=0369A1&label=size" alt="Repository Size" />
	<a href="https://www.repostatus.org/#active"><img src="https://www.repostatus.org/badges/latest/active.svg" alt="Project Status: Active" /></a>
</p>

<p align="center">
	<img src="https://img.shields.io/badge/Node.js-18.x%20%7C%2020.x-339933?style=flat-square&logo=node.js&logoColor=white" alt="Node.js" />
	<img src="https://img.shields.io/badge/React-19.x-61DAFB?style=flat-square&logo=react&logoColor=111827" alt="React" />
	<img src="https://img.shields.io/badge/Python-3.11.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
	<img src="https://img.shields.io/badge/PyTorch-2.5.1-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch" />
	<img src="https://img.shields.io/badge/MySQL-8.x-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL" />
</p>

<p align="center">
	<a href="#quick-overview">Quick overview</a> | <a href="#production-pipeline">Production Pipeline</a> | <a href="#system-blueprint">System Blueprint</a> | <a href="#quick-launch">Quick Launch</a> | <a href="#team">Team</a>
</p>

---

## Quick overview

> Upload one street-level image.
> 
> HistoriClip identifies the landmark, proves geometric authenticity, writes a documentary script, generates stylized historical scenes, and renders a narrated documentary video automatically.

| Input | Intelligence | Output |
|---|---|---|
| Landmark photo | Vision + XAI + LLM + Diffusion + Video synthesis | Historical mini-documentary |

---

## Demo

<p align="center">
  <video src="https://github.com/user-attachments/assets/b76506a0-d503-4f85-89a9-f381be5edfba" width="100%" controls autoplay loop muted></video>
</p>

---

## Production Pipeline

<p align="center">
  <img src="project_diagrams/production_pipeline.png" alt="Production Pipeline Diagram" width="100%" />
</p>


| Stage | Engine |
|---|---|
| Detection | DINOv2 + FAISS |
| Verification | DISK + LightGlue |
| Script | Google Gemini |
| Visuals | SDXL Lightning |
| Rendering | gTTS + FFmpeg + Ken Burns |

**What makes this special?**

- Structural verification is not a guess; keypoint matching provides visual evidence.
- Narrative and visuals are generated as one coherent timeline.
- The final output is not just images; it is a paced, narrated documentary video.

---

## System Blueprint

<p align="center">
  <img src="project_diagrams/system_blueprint.png" alt="System Blueprint Diagram" width="100%" />
</p>

| Layer | Responsibility | Core Stack |
|---|---|---|
| Frontend | Upload, playback, history, XAI view | React 19, Vite, TailwindCSS |
| Backend | Auth, orchestration, persistence, APIs | Node.js, Express, MySQL |
| AI Service | Recognition, verification, generation, stitching | Python, Flask, PyTorch |

---

## Quick Launch

1. Read setup guide: [`HistoriClip-v2/INSTALLATION.md`](./HistoriClip-v2/INSTALLATION.md)
2. Install prerequisites: `Miniconda`, `CUDA 12.1`, `Node 18/20`, `MySQL`, `FFmpeg`
3. Add API keys in `.env`: `Gemini`, `Google Vision`, `Mapillary`
4. Start services:
	 - Windows: `windows_start.bat`
	 - Linux/macOS: `./start.sh`
5. Open `http://localhost:5173`

---

## Team

| Contributor |
|---|
| Onkar Kundaram |
| Vishwas Kude |
| Prajwal Khobragade |

---

## License

Personal/academic final-year project. All rights reserved by the original authors.

<p align="center">
	<img src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer&color=0:0EA5E9,100:0F172A" alt="Footer" />
</p>
