# HealthMind UI

Premium light theme React + Vite + Tailwind CSS frontend for the Medical Knowledge RAG API.

## Setup

```bash
npm install
```

## Configure API

Copy `.env.example` to `.env` and set your API URL:

```
VITE_API_URL=http://localhost:8000/api/v1
```

## Development

```bash
npm run dev
```

## Production Build

```bash
npm run build
npm run preview
```

## Features

- **Authentication** — Register, login, JWT refresh
- **Chat Interface** — ChatGPT-style conversation sidebar with grouping (Today / Yesterday / Earlier)
- **RAG Queries** — Send queries, view AI responses with cited sources & retrieval metadata
- **Document Management** — Drag-and-drop upload, status tracking (processing/ready/error), per-conversation KB
- **Adjustable Top-K** — Configure retrieval count per query
- **Admin Panel** — System stats, user management, role assignment, enable/disable users
- **Premium Light Theme** — Cormorant Garamond + DM Sans typography, warm cream palette, teal accent

## Tech Stack

- React 18 + Vite
- Tailwind CSS v3
- Lucide React icons
- React Router DOM
