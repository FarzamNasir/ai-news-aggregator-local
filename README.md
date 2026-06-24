# Lumin: AI News Aggregator

An automated pipeline and web platform that scrapes AI news from top research sources, generates LLM-powered summaries, and delivers personalized daily email digests tailored to each user's specific domains of interest.

🔗 **Live Project:** [lumin-ai-news.onrender.com](https://lumin-ai-news.onrender.com/)

---

## What it is

AI moves fast. Between new arXiv papers, blog posts from major labs, and daily YouTube breakdowns, keeping up is a full-time job. 

**Lumin** solves this by:
1. **Scraping** the most important AI sources daily (YouTube, OpenAI, Anthropic, Meta, Hugging Face, arXiv).
2. **Summarizing** every piece of content using fast LLMs (Groq / Llama 3.3).
3. **Curating** articles uniquely for each user based on their chosen domains.
4. **Delivering** a beautiful, personalized HTML email digest straight to your inbox.

No accounts to manage. Users just pick their domains, enter their email, and receive their curated news.

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        YT["🎬 YouTube Channels"]
        BL["📝 AI Labs\n(OpenAI, Meta, Anthropic, HF)"]
        AX["📄 arXiv Papers"]
    end

    subgraph Pipeline (Cron Job)
        S["⛏️ Scraper\nFetch & Deduplicate"]
        D["🧠 Digest Agent\nLlama 3.3 70B\nSummarization"]
        C["🎯 Curator Agent\nLlama 3.3 70B\nRelevance Scoring"]
        E["✉️ Email Agent\nPersonalized Intro + Render"]
    end
    
    subgraph Web App (FastAPI)
        UI["🌐 Landing Page\nSubscribe & Manage"]
    end

    DB[("🗄️ PostgreSQL\narticles, users, digests")]
    SMTP["📬 Gmail SMTP\nHTML Email Delivery"]

    YT & BL & AX --> S
    S --> DB
    DB --> D
    D --> DB
    UI <--> DB
    DB --> C
    C --> E
    E --> SMTP
```

### The Pipeline
1. **Scrape**: Fetches recent content across multiple sources. Parses RSS, extracts YouTube transcripts, and deduplicates URLs.
2. **Digest**: Uses **Groq (Llama-3.3-70b-versatile)** via structured outputs to generate concise, standardized titles and 2-3 sentence summaries for every article.
3. **Curate**: Fetches all active subscribers. For each user, the LLM batch-scores (1-10) all new articles against their specific domains and custom notes.
4. **Deliver**: The top articles are selected, the LLM writes a personalized greeting, and the system renders a monochromatic, responsive HTML email.

## Tech Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.12 |
| **Package Manager** | uv |
| **Web Framework** | FastAPI (with Uvicorn) |
| **Frontend** | Vanilla HTML/CSS/JS + GSAP Animations (Glassmorphism design) |
| **Database** | PostgreSQL 16 + SQLAlchemy ORM |
| **LLM Provider** | Groq (Llama 3.3 70B) — chosen for blazing-fast batch inference |
| **HTTP Client** | httpx |
| **Email** | smtplib + email.mime (Gmail SMTP) |
| **Infrastructure**| Render (Web Service + Cron Job + Managed DB) |

## Repository Structure

```text
app/
├── api/                   # FastAPI application & routes
│   └── main.py            # Entrypoint for the web server
├── static/                # Frontend assets (HTML, CSS, JS)
├── config.py              # Environment and source configurations
├── runner.py              # Cron job pipeline orchestrator
├── scrapers/
│   ├── base.py            # Base RSS scraper logic
│   ├── youtube.py         # YouTube RSS + transcripts
│   ├── arxiv_scraper.py   # arXiv cs.AI, cs.LG, cs.CL
│   ├── huggingface_blog.py# Hugging Face RSS
│   ├── meta_blog.py       # Meta AI RSS
│   └── ...                # OpenAI, Anthropic
├── database/
│   ├── models.py          # SQLAlchemy models (Article, Digest, Subscriber)
│   ├── connection.py      # DB engine
│   └── repository.py      # CRUD operations
└── agent/
    ├── summarizer.py      # Article summarization agent
    ├── curator.py         # Relevance scoring agent
    ├── email_agent.py     # Intro generation
    └── email_sender.py    # HTML rendering and SMTP delivery
```

## Deployment
Lumin is fully deployed on Render using a declarative `render.yaml` blueprint.

The infrastructure consists of three components:
1. **news-aggregator-db**: A managed PostgreSQL instance.
2. **lumin-ai-news**: A FastAPI web service hosting the frontend UI and subscription APIs.
3. **ai-news-digest**: A background cron job that wakes up daily, runs the scraping/curation pipeline (`uv run python -m app.runner`), sends the emails, and spins back down.
