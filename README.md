<h1 align="center">⚡ The Flash Auto Filter Bot ⚡</h1>

<p align="center">
  <b>Speed Beyond Limits — High-Speed Telegram Auto-Filter, File Indexing, 3-Step Verification, Premium Engine & Instant Media Streaming Bot.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/Framework-Pyrogram%20v2-orange?style=for-the-badge" alt="Pyrogram">
  <img src="https://img.shields.io/badge/Database-MongoDB-green?style=for-the-badge&logo=mongodb" alt="MongoDB">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<p align="center">
  <a href="https://t.me/PspkmovieXBot">
    <img src="https://img.shields.io/badge/Bot-@PspkmovieXBot-blue?style=for-the-badge&logo=telegram" alt="Bot Link">
  </a>
  <a href="https://t.me/You_Want_To_Know_Me">
    <img src="https://img.shields.io/badge/Owner-[Rox࿐Star✧]-red?style=for-the-badge&logo=telegram" alt="Owner Link">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Speed-Flash%20Mode-yellow?style=flat-square&logo=lightning" alt="Flash Speed">
  <img src="https://img.shields.io/badge/Auto%20Filter-Ultra%20Fast-ff69b4?style=flat-square" alt="Auto Filter">
  <img src="https://img.shields.io/badge/Streaming-Online%20%26%20Download-orange?style=flat-square" alt="Streaming">
  <img src="https://img.shields.io/badge/Premium-Plan%20Stacking-purple?style=flat-square" alt="Premium">
  <img src="https://img.shields.io/badge/FSub-Auto%20Leave%20Alert-red?style=flat-square" alt="FSub Alert">
</p>

---

**The Flash** is an advanced, ultra-responsive Telegram modular Auto-Filter bot engineered for lightning-speed file indexing, instant database retrieval, in-browser fast streaming, smart spell corrections, automated multi-tier verification, and complete subscription management.

> ⚡ *Built with Pyrogram v2 & Motor Async MongoDB for seamless scale and zero lag.*

---

## 📑 Table Of Contents

- [Key Highlights](#-key-highlights)
- [Requirements](#-requirements)
- [Environment Variables](#-environment-variables)
- [Deploy On Heroku](#-deploy-on-heroku)
- [Deploy On Render](#-deploy-on-render)
- [Deploy With Docker](#-deploy-with-docker)
- [Local Setup](#-local-setup)
- [Commands](#-commands)
- [Security & Public Forks](#-security--public-forks)
- [Developer & Credits](#-developer--credits)

---

## ⚡ Key Highlights

| 🔍 Search & Indexing | 🛡️ Access & Subscription | ⚡ Web & Streaming Engine |
| :--- | :--- | :--- |
| **Ultra-Fast Search:** Millisecond file delivery | **Auto Leave Alert:** Notifies user upon leaving channel | **Online Video Stream:** Browser video player |
| **Smart Fuzzy Matching:** AI spelling suggestions | **Smart Plan Stacking:** Preserves remaining active days | **Direct Download Links:** High-speed chunk downloads |
| **Multi-DB Support:** Auto-switches to secondary cluster | **3-Tier Verification:** Custom shorteners with time-gaps | **Dynamic Post Generator:** TMDB landscape banners |
| **Episode Grouping:** Compact series batch layout | **Trial Engine:** Instant 5-minute automated free pass | **Media Information:** Quick Telegraph track extractor |

---

## 📦 Requirements

- Python 3.11 or 3.12+
- MongoDB Database cluster (Atlas or self-hosted)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Telegram `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org)
- Private Channel for `BIN_CHANNEL` & `LOG_CHANNEL`

---

## ⚙️ Environment Variables

### Mandatory Settings

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Telegram bot token obtained from [@BotFather](https://t.me/BotFather) |
| `API_ID` | Telegram API identifier from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API hash string from [my.telegram.org](https://my.telegram.org) |
| `DATABASE_URI` | Primary MongoDB Atlas connection string |
| `DATABASE_NAME` | Primary Database name (e.g. `TheFlashBot`) |
| `ADMINS` | Space-separated User IDs of administrators/owners |
| `BIN_CHANNEL` | Channel ID for file streaming & temporary storage (`-100...`) |
| `LOG_CHANNEL` | Channel ID for system logs & exceptions (`-100...`) |

### Optional & Advanced Configurations

| Variable | Default | Description |
| :--- | :--- | :--- |
| `URL` / `FQDN` | Dynamic | App domain for stream links (e.g., `https://your-app.herokuapp.com/`) |
| `AUTH_CHANNELS` | `-100...` | Force-subscription channel IDs (separated by spaces) |
| `AUTH_REQ_CHANNELS` | `-100...` | Request-to-join force subscription channels |
| `CHANNELS` | Empty | Channels from which media is indexed automatically |
| `SUPPORT_CHAT_ID` | `-100...` | Support group chat ID |
| `MULTIPLE_DB` | `False` | Enable multi-database fallback |
| `DATABASE_URI2` | Empty | Secondary MongoDB connection string |
| `IS_VERIFY` | `False` | Enable 3-step shortener verification flow |
| `TMDB_API_KEY` | Empty | Metadata key for fetching HD backdrop posters |
| `DELETE_TIME` | `300` | Auto-delete interval in seconds |

---

## 🚀 Deploy On Heroku

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

1. Fork or push this repository to your GitHub profile.
2. Click the **Deploy to Heroku** button above.
3. Fill in your environment credentials in the config vars table.
4. Scale the `web` process to `1` in the Resources tab.

---

## 🌐 Deploy On Render

1. Create a new **Web Service** on [Render](https://render.com).
2. Connect your GitHub repository.
3. Select **Docker** as the Runtime environment.
4. Under **Environment Variables**, fill in your credentials from the table above.
5. Provide a valid `PORT` (default `8080`) and set:
   ```env
   FQDN=your-app-name.onrender.com
   HAS_SSL=True
   NO_PORT=True
