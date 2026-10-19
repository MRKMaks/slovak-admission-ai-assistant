# 🎓 AI Form Filler

<div align="center">
  <p><strong>An intelligent, conversational AI assistant for automated filling of the Slovak university admission form.</strong></p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-blue.svg" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.109-009688.svg" />
    <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-336791.svg" />
    <img alt="uv" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" />
  </p>
</div>

---

## 📖 Overview

The **AI Form Filler** leverages the power of Large Language Models to gather necessary data from users step-by-step through a natural conversation. Once all required information is collected, it automatically generates a print-ready PDF document matching the strict government template.

### ✨ Key Features
- **🧠 Intelligent Dialog:** Asks context-aware questions until all form fields are satisfied.
- **📄 Pixel-Perfect PDF Generation:** Uses LibreOffice headless mode to convert DOCX templates precisely.
- **💾 Session Persistence:** Saves conversations to a PostgreSQL database, allowing you to resume later.
- **⚡ Lightning Fast:** Powered by FastAPI and Astral's `uv` package manager for instant builds.
- **🐳 Fully Containerized:** One-command deployment via Docker Compose.

---

## 🛠 Architecture & Tech Stack

- **Backend:** FastAPI, Python 3.11+
- **Package Manager:** `uv` (Astral)
- **Database:** PostgreSQL 16 (asyncpg + SQLAlchemy 2.0 + Alembic)
- **Data Validation:** Pydantic V2
- **LLM Integration:** Ollama
- **Document Generation:** `docxtpl` (Jinja2 for `.docx`) + LibreOffice (export to `.pdf`)
- **CLI Client:** `typer` + `rich` (beautiful interactive console UI)

---

## 🚀 Getting Started (Docker Recommended)

Everything, including the API, Database, and LibreOffice, is fully containerized. This is the safest way to run the application because it ensures all dependencies (like LibreOffice for PDF generation) are present.

### 1. Environment Setup
Copy the example environment file:
```bash
cp .env.example .env
```
*(Make sure to adjust the `LLM_PROVIDER`, `OLLAMA_HOST`, and `LLM_MODEL` inside `.env` to match your Ollama setup. For Docker, `OLLAMA_HOST=http://host.docker.internal:11434` works best for a local Ollama).*

### 2. Start the Infrastructure
Build and start the PostgreSQL database and FastAPI backend:
```bash
docker compose up --build -d
```

### 3. Run Database Migrations
Apply the initial schema to the database running inside the container:
```bash
docker compose exec api uv run alembic upgrade head
```

### 4. Talk to the Assistant
To start filling the form, run the interactive CLI directly inside the API container:
```bash
docker compose exec api uv run cli.py
```

---

## 💬 Usage (CLI Client)

Talk to the AI assistant using the interactive console client. It will ask you for information until the form is complete.

**Start a new session:**
```bash
docker compose exec api uv run cli.py
```

**Resume a past session:**
If you closed the application or the server restarted, you can continue exactly where you left off by providing your Session ID (which is printed at the start of every session):
```bash
docker compose exec api uv run cli.py --session-id your_session_id
```

*Note: You can specify a custom API URL using `--url http://localhost:8000`*

---

## 📝 Example Scenarios (Test Prompts)

Here are three pre-made text inputs you can copy and paste into the CLI to instantly complete the form in different scenarios.

### 👤 Sample 1 (Standard Slovak Citizen)
> Volám sa Ján Novák, narodil som sa 15. mája 2005 v Bratislave. Moje rodné číslo je 050515/1234. Som Slovák, muž. Bývam na Hlavnej 10, Bratislava, PSČ 811 01, okres Bratislava I, Slovensko. Nemám inú korešpondenčnú adresu. Telefón mám 0901234567, email jan.novak@gmail.com. Hlásim sa na Slovenskú technickú univerzitu, Fakulta informatiky a informačných technológií, program Aplikovaná informatika, denná prezenčná forma. Prijímačky z angličtiny. Zmaturoval som v máji 2024 na Gymnáziu Jura Hronca, Novohradská 3, Bratislava, 821 09, okres Bratislava II. Kód školy 123456789, študijný odbor gymnázium, kód 7902J, stupeň úplné stredné všeobecné. Známky zo slovenčiny: 1, 1, 1, 1. Maturita zo slovenčiny B2, externá 80%, písomná 90%, ústna 1. Prílohy: ročníkové vysvedčenia. Súhlasím so spracovaním údajov. V minulosti som na VŠ neštudoval. Vytvor pdf.

### 🏠 Sample 2 (Slovak Citizen with Correspondence Address & Previous Study)
> Som Mária Kováčová (rod. Malá), narodená 10.10.2000 v Košiciach. RČ: 006010/9876. Občianstvo slovenské, žena. Trvalý pobyt: Kováčska 5, Košice, 040 01, okres Košice I, Slovensko. Korešpondenčná adresa: Letná 9, Prešov, 080 01, okres Prešov. Tel: 0911000111, email: maria@test.sk. Hlásim sa na Univerzitu Komenského, Prírodovedecká fakulta, biológia, externá dištančná forma. Zmaturovala som 06/2019 na Strednej odbornej škole, Jarná 1, Košice, 040 01, okres Košice I. Kód 987654321, odbor zdravotnícky asistent, kód 5356M, úplné stredné odborné. Známky biológia: 1, 2, 1, 1. Maturita z biológie: externá 90%, písomná 85%, ústna 2. V minulosti som študovala na Technickej univerzite v Košiciach, fakulta umení, dizajn, bakalársky stupeň, od 2019 do 2022. Prílohy: maturitné vysvedčenie, VŠ diplom. Súhlasím so spracovaním údajov. Vytvor pdf.

### 🌍 Sample 3 (Foreigner Resident in Slovakia)
> Som Ivan Maly, muž, narodený 12.12.2004 v Kyjeve, Ukrajina. Štátne občianstvo: UKRAJINSKÉ. Rodné číslo: 041212/0000. Trvalé bydlisko: Tarasa Shevchenka 15, Kyjev, 01001, okres Kyjev, Ukrajina. Miesto pobytu u cudzinca na SR: Štúrova 5, Košice, 040 01, okres Košice I, Slovensko. Tel 0944111222, email ivan@maly.ua. Hlásim sa na Technickú univerzitu, Strojnícka fakulta, mechatronika, denná kombinovaná forma. Zmaturoval som 06/2022 na Strednej škole č. 15, Velyka 1, Kyjev, 01001, okres Kyjev, Ukrajina. Kód školy 000000, odbor iná (všeobecné), kód 0000, úplné stredné vzdelanie. Nemám známky ani maturitu, dodám v prílohe. Prílohy: KÓPIA DOKLADU O VZDELANÍ, ÚRADNÝ PREKLAD DOKLADU. V minulosti som na VŠ neštudoval. Súhlasím so spracovaním údajov. Vytvor pdf.

---
*Developed by Maksym (MRKMaks).*