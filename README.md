# X (Twitter) Interaction AI Agent

<p align="center">
  <a href="https://youtu.be/HXYUNBy6mJM" target="_blank">
    <img src="assets/demo_thumbnail.png" alt="X AI Agent Demo Video" width="100%" />
  </a>
</p>

<p align="center">
  🎬 <b><a href="https://youtu.be/HXYUNBy6mJM" target="_blank">Watch the Full Live Demo Walkthrough on YouTube (Click Image to Play)</a></b>
</p>

---

An intelligent, autonomous interaction system for X (Twitter) built on Python, Playwright, Pydantic, SQLite, and Google Gemini.

Designed strictly around the core architecture principle: **"The AI plans. The deterministic system executes."**

---

## 🏛️ Architecture Pipeline

```text
       ┌─────────────┐
       │   OBSERVE   │  Playwright Browser Layer (Feed Navigation & Post Discovery)
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │   EXTRACT   │  DOM Post Element Extractor (Text, Author, Engagements)
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │  NORMALIZE  │  Whitespace, Counts, URLs, Deduplication
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │    PLAN     │  AI Planner (Gemini API / Free ChatGPT Web --jugad / Mock)
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │  VALIDATE   │  Deterministic Rule, Allowlist & Budget Validator
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │   EXECUTE   │  Verified Playwright Execution (Like / Comment / Reply)
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │  DEEP DIVE  │  (Optional) Explore & Interact with Inner Thread Comments
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │   VERIFY    │  Post-Action DOM State Verification
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │  REMEMBER   │  Persistent SQLite History (Prevent duplicates & track runs)
       └─────────────┘
              │
              ▼
        DISCOVER MORE
```

---

## ✨ Key Features

- **Strict AI Boundaries**: The LLM outputs structured decisions (`like`, `comment`, `reply`, `skip`). It cannot run raw browser commands, selectors, or scripts.
- **Dual AI Planning Methods**:
  - **Gemini API (Default)**: Fast, structured JSON via `google-genai` SDK.
  - **`--jugad` Mode (Free ChatGPT Web)**: Automates `https://chatgpt.com` via Playwright with automatic copy-button extraction, rate-limit recovery, and zero API token cost.
  - **`--mock-ai` Mode**: Deterministic offline simulation for testing without external models.
- **Deep Dive Thread Exploration (Enabled by default)**:
  - When an exceptionally interesting startup/dev post is found, the agent dives inside the post.
  - Interacts with relevant inner thread comments/replies up to the configurable limit (default: 10).
  - Automatically returns back to the main feed to continue scrolling.
- **Interaction & Scroll Budget Enforcement**: Configurable global interaction limits (`-n`), scroll limits (`-s`), and inner thread limits (`-i`).
- **Persistent Sessions**: Reusable Chromium profiles for both X (`browser_data/x_profile/`) and ChatGPT (`browser_data/chatgpt_profile/`).
- **SQLite Interaction Memory**: Records all actions with SQLite indexes to eliminate duplicate interactions across runs.
- **Developer Persona**: Pre-tuned for casual, organic engagement on startups, product launches, developer takes, and job openings.

---

## 🚀 Quick Start & Setup

### 1. Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or standard `pip`

```bash
# Install dependencies with uv
uv sync

# Install Playwright browser binaries
uv run playwright install chromium
```

### 2. Configuration (`.env`)

Create a `.env` file in the project root:

```env
# Gemini API Key (Required for default live AI planning)
GEMINI_API_KEY=your_gemini_api_key_here

# Target URL (Home feed, search query, or profile)
TARGET_PAGE=https://x.com/home

# Interaction Budget Limits
MAX_INTERACTIONS=10
MAX_SCROLL_ATTEMPTS=10
MAX_INNER_INTERACTIONS=10
DEEP_DIVE_ENABLED=true

# Allowed Actions
ALLOWED_ACTIONS=["like", "comment", "reply"]

# Browser settings
HEADLESS=false
USER_DATA_DIR=./browser_data/x_profile
CHATGPT_USER_DATA_DIR=./browser_data/chatgpt_profile
DATABASE_PATH=./data/interactions.db

# User Profile & Strategic Engagement Goal
USER_PROFILE="Full-stack developer with 1 year and 8 months of experience. Works with React, Next.js, Node.js, Python, TypeScript. Passionate about early-stage startups, indie products, and job openings."
INTERACTION_GOAL="Engage casually and organically with new startups, dev launches, tech openings, and developer takes. Drop short, friendly comments, leave likes, and build genuine connections."
```

---

## 🔑 Authentication & One-Time Logins

Playwright uses persistent browser profile directories so you only need to log in **once**.

### 1. Log in to X (Twitter)
```bash
uv run python main.py --login
```
1. Chromium opens to `https://x.com/login`.
2. Log into your X account and complete 2FA.
3. Return to the terminal and press **ENTER**.
4. Saved in `browser_data/x_profile/`.

### 2. Log in to ChatGPT (for `--jugad` mode)
```bash
uv run python main.py --login-chatgpt
```
1. Chromium opens to `https://chatgpt.com`.
2. Log into your OpenAI / Google / Apple account.
3. Return to the terminal and press **ENTER**.
4. Saved in `browser_data/chatgpt_profile/`.

---

## 🛠️ CLI Flags & Options Reference

| Flag / Option | Aliases | Description | Default |
| :--- | :--- | :--- | :--- |
| `-n` | `--count`, `--limit`, `--target-posts`, `--max-interactions` | Target number of interactions/posts to perform in the run | `10` |
| `-s` | `--max-scrolls`, `--max-scroll-attempts`, `--scroll-limit` | Maximum feed scroll attempts before stopping | `10` |
| **`-i`** | **`--max-inner-interactions`, `--inner-limit`, `--inner-interactions`** | **Max comments to interact with inside a single post thread** | **`10`** |
| **`--no-deep-dive`** | **`--disable-deep-dive`** | **Disable diving inside posts to interact with thread comments** | *(Deep Dive is enabled by default)* |
| `--deep-dive` | *(none)* | Explicitly enable diving inside posts | `True` |
| `--target-url` | *(none)* | Target URL (Home feed, search query, or list) | `https://x.com/home` |
| `--jugad` | *(none)* | Use free ChatGPT Web interface via Playwright (zero API cost) | `False` |
| `--mock-ai` | *(none)* | Use deterministic offline mock planner | `False` |
| `--dry-run` | *(none)* | Simulate discovery, planning, and validation without clicking/typing | `False` |
| `--login` | *(none)* | Open interactive browser to log in to X (Twitter) | `False` |
| `--login-chatgpt` | *(none)* | Open interactive browser to log in to ChatGPT | `False` |
| `--headless` | *(none)* | Run browser in background without opening GUI window | `False` |
| `--debug` | *(none)* | Enable detailed debug level logging | `False` |

---

## 💡 Practical CLI Examples

### 1. Default Run (Gemini API + Deep Dive)
```bash
# Run with default 10 interactions, exploring thread comments inside interesting posts
uv run python main.py

# Target 5 total interactions with max 2 comments per thread deep dive
uv run python main.py -n 5 -i 2

# Disable deep dive (only interact with main feed posts)
uv run python main.py --no-deep-dive -n 10
```

### 2. Free ChatGPT Web Mode (`--jugad`)
```bash
# Run with free ChatGPT Web planner + Deep Dive enabled
uv run python main.py --jugad

# Target 5 interactions, 5 scrolls, max 3 thread replies
uv run python main.py --jugad -n 5 -s 5 -i 3

# Custom search feed + ChatGPT Web planner + 8 post limit + 5 scrolls limit
uv run python main.py --jugad --target-url "https://x.com/search?q=buildinpublic&f=live" -n 8 -s 5
```

### 3. Targeting Search Feeds & Topics
```bash
# Target tech startup launch tweets with thread comment engagement
uv run python main.py --target-url "https://x.com/search?q=startup%20launch&f=live" -n 10 -i 3

# Target developer job openings
uv run python main.py --target-url "https://x.com/search?q=hiring%20fullstack%20remote&f=live" -n 5 -s 8
```

### 4. Testing & Dry-Run Simulations
```bash
# Test the complete pipeline safely without clicking or liking
uv run python main.py --dry-run -n 5 -i 2

# Test offline with Mock Planner (no API keys, no external browser for LLM)
uv run python main.py --mock-ai --dry-run -n 5

# Run in background (headless) with debug logs
uv run python main.py --headless --debug -n 5
```

---

## 📂 Project Structure

```text
├── PROJECT.md               # Primary project specifications
├── AGENTS.md                # Safety rules and architectural constraints
├── pyproject.toml           # Project dependencies and configuration
├── main.py                  # Root CLI entry point
│
├── app/
│   ├── config.py            # Pydantic Settings & environment config
│   │
│   ├── models/              # Pydantic domain models
│   │   ├── post.py          # Raw, Author, and NormalizedPost models
│   │   ├── action.py        # ProposedAction, ActionPlan, ValidatedAction
│   │   ├── result.py        # ExecutionResult and ExecutionStatus
│   │   └── run_state.py     # RunState, RunMetrics, RunStatus
│   │
│   ├── browser/             # Playwright browser automation
│   │   ├── session.py       # Session and persistent context management
│   │   ├── login.py         # Interactive X login routine
│   │   ├── navigator.py     # Navigation, element waiting, go_back, and scrolling
│   │   ├── scraper.py       # Tweet DOM discovery and thread reply extraction
│   │   └── executor.py      # Like & comment execution and verification
│   │
│   ├── extraction/          # Data parsing and normalization
│   │   ├── parser.py        # DOM parser for tweet locators
│   │   ├── normalizer.py    # Text cleaning, handle normalization, count parsing
│   │   └── deduplicator.py  # Session & batch deduplication
│   │
│   ├── planner/             # AI Decision layer
│   │   ├── base.py          # BasePlanner abstract class
│   │   ├── planner.py       # Google GenAI integration & MockPlanner
│   │   ├── chatgpt_web.py   # Free ChatGPT Web Playwright planner (--jugad)
│   │   ├── login_chatgpt.py # Interactive ChatGPT login routine
│   │   ├── prompts.py       # Token-optimized structured prompt builders
│   │   └── schemas.py       # ActionPlan schema definitions
│   │
│   ├── validation/          # Deterministic control layer
│   │   └── action_validator.py # Budget, allowlist, duplicate, content validation
│   │
│   ├── memory/              # SQLite persistent history
│   │   ├── models.py        # InteractionRecord schema
│   │   └── repository.py    # Async SQLite queries and indexes
│   │
│   ├── services/            # Orchestration layer
│   │   └── run_service.py   # Complete runtime loop & Deep Dive thread execution
│   │
│   └── observability/       # Logging and error definitions
│       └── logging.py       # Structured logger and custom exceptions
│
└── tests/                   # Pytest test suite
    ├── conftest.py          # Fixtures and test setup
    ├── test_normalizer.py   # Normalizer and deduplicator tests
    ├── test_validator.py    # Deterministic validator tests
    ├── test_memory.py       # SQLite repository tests
    ├── test_planner.py      # Planner and prompt tests
    ├── test_chatgpt_web.py  # ChatGPT Web JSON parsing tests
    └── test_runtime.py      # End-to-end integration & Deep Dive tests
```

---

## 🧪 Testing

Run the full pytest suite:

```bash
uv run pytest -v
```
