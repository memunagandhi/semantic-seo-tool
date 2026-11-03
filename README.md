# MGwix SemanticIR Studio: Dense Retrieval & Cross-Encoder AEO Tool

A standalone Information Retrieval (IR) and Semantic SEO evaluation studio built with Python, Flask, SQLite/PostgreSQL, and Cohere Cross-Encoder Rerank API.

## Features
- **Dense Retrieval Engine:** Bi-encoder semantic vector embeddings with Cosine Similarity.
- **Cross-Encoder Reranking:** Cohere v3.5 deep relevance model (`rerank-v3.5`) scoring.
- **Answer Engine Optimization (AEO):** Gauge confidence score for Google AI Overviews and Perplexity citations.
- **Topical Gap Detector:** Identifies missing entity words and suggests actionable heading/lead copy improvements.
- **Dual-Engine Architecture:** Runs live with `COHERE_API_KEY` or locally with zero external dependencies.
- **Database Backed:** Stores all analysis history with SQLite (local) or PostgreSQL (Render).
- **Excel Export:** Download complete evaluation history in `.xlsx` format.

---

## Local Setup & Quick Start

1. **Navigate to this directory:**
   ```bash
   cd semantic-seo-tool
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set required secrets** (use strong, unique values; do not commit them):
   ```powershell
   $env:FLASK_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
   $env:APP_PASSWORD = (python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

4. **Run the web application:**
   ```bash
   python app.py
   ```
   Sign in at `http://127.0.0.1:5001`. Set `COHERE_API_KEY` as an environment
   variable if you want to enable live Cohere calls.

---

## Deploying separately on Render (with PostgreSQL)

This folder is self-contained: it includes the Flask app, templates, CSS/JS,
dependencies, and a Render Blueprint. To host it separately from the MGwix
website, put the **contents of this folder** in a separate GitHub repository.

1. Push this folder's contents to its own GitHub repository, with `render.yaml`
   at the repository root.
2. In the [Render Dashboard](https://dashboard.render.com), choose **New +** →
   **Blueprint**, then select that repository.
3. Render will create the web service **`mgwix-semantic-ir-tool`** and the
   PostgreSQL database **`mgwix-semantic-db`** from `render.yaml`. The service's
   `DATABASE_URL` is connected to that database automatically.
4. Set the required `APP_PASSWORD` in the Blueprint prompt to a strong,
   unique password (at least 16 characters; a generated password is
   recommended). Render generates `FLASK_SECRET_KEY` automatically.
5. Optionally set `COHERE_API_KEY` in the web service's environment settings to
   enable live Cohere reranking. Without it, the local simulation engine works.

The app requires sign-in for all pages and analysis endpoints. API keys are
read only from environment variables, not entered in the web UI or stored in
the app database. Keep `APP_PASSWORD`, `FLASK_SECRET_KEY`, and `COHERE_API_KEY`
private; rotate the Cohere key if it is ever exposed.

You do **not** need to run SQL or manually create tables. On startup, the app
creates its tables in PostgreSQL. Do not deploy the local `semantic_tool.db`;
`.gitignore` excludes it, and Render uses the PostgreSQL `DATABASE_URL`.
