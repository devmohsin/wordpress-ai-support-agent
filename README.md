# AI Support Agent for WordPress & SaaS

A self-hosted AI customer support chatbot that trains on your product documentation and answers user questions instantly — 24/7, on your own server.

## What it does

- **Crawls your docs** — paste a URL and it indexes every page automatically
- **Answers product-specific questions** — Claude AI with RAG, only uses your content
- **Smart escalation** — flags billing, refunds, and frustrated users for your human team
- **Embeddable widget** — one script tag to add the chat bubble to any site
- **Admin dashboard** — see all conversations, stats, and escalations in real time

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| AI | Claude API (claude-haiku) · Anthropic SDK |
| Vector DB | ChromaDB (local, persistent) |
| Scraper | aiohttp · BeautifulSoup4 |
| Frontend | Vanilla HTML/CSS/JS (no framework) |

## Project Structure

```
wordpress-ai-support-agent/
├── backend/
│   ├── main.py           # FastAPI app — all API routes
│   ├── scraper.py        # Async documentation crawler
│   ├── vector_store.py   # ChromaDB vector storage & search
│   ├── chat_engine.py    # Claude API integration with RAG
│   ├── models.py         # Pydantic request/response models
│   └── requirements.txt
├── frontend/
│   ├── index.html        # Landing page + onboarding form
│   ├── admin.html        # Admin dashboard
│   ├── css/
│   │   ├── main.css      # Global styles
│   │   └── widget.css    # Chat widget styles
│   └── js/
│       ├── widget.js     # Embeddable chat widget
│       └── admin.js      # Dashboard logic
├── .env.example
└── .gitignore
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/devmohsin/wordpress-ai-support-agent.git
cd wordpress-ai-support-agent
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure your API key

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
# Get a key at: https://console.anthropic.com
```

### 4. Start the server

```bash
cd backend
python main.py
```

The server runs at `http://localhost:8000`. Open your browser and go there — the landing page will load automatically.

## How to onboard a client

1. Open `http://localhost:8000`
2. Enter the client's **product name** and **docs URL**
3. Click **Index Documentation** — the agent crawls and indexes all pages (2–3 min)
4. Copy the generated **embed snippet**
5. Paste it into the client's WordPress site before `</body>`

The agent is now live on their site.

## Embed snippet format

```html
<script>
  window.AISupportConfig = {
    agentId:   "your-product",
    agentName: "Your Product Support",
    apiBase:   "https://your-server.com"
  };
</script>
<script src="https://your-server.com/js/widget.js"></script>
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/onboard` | Crawl & index a docs URL |
| `GET`  | `/api/onboard/status/{job_id}` | Poll indexing job status |
| `POST` | `/api/chat` | Send a message, get an AI response |
| `POST` | `/api/feedback` | Submit thumbs up/down rating |
| `GET`  | `/api/conversations` | Admin: list all conversations |
| `GET`  | `/api/conversations/{id}` | Admin: get full conversation |
| `GET`  | `/api/stats` | Admin: dashboard summary stats |
| `DELETE` | `/api/knowledge-base/{agent_id}` | Wipe and re-index an agent |

## Deployment (VPS / Docker)

For production, run behind a reverse proxy (nginx) with HTTPS. The `chroma_db/` directory persists your knowledge base — back it up regularly.

```bash
# Example: run with gunicorn for production
pip install gunicorn
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Author

**Mohsin** — [github.com/devmohsin](https://github.com/devmohsin)
