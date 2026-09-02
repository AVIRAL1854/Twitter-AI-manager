# PROJECT.md --- X Interaction AI Agent

> **Project Source of Truth**
>
> This document defines what the project is, why it exists, how every
> layer works, how data moves through the system, what each component
> owns, and the implementation roadmap.
>
> When making architecture or implementation decisions, this document
> and `AGENTS.md` should be treated as the primary project references.

---

# 1. Executive Summary

## What are we building?

We are building an **AI-assisted X (Twitter) interaction system**.

The system will:

- Open an X page or feed using Playwright.
- Discover and read visible posts.
- Extract relevant post information.
- Convert raw browser data into structured objects.
- Give those objects to an AI planning layer.
- Let the AI decide which posts are worth interacting with.
- Generate a structured action plan.
- Validate every proposed action.
- Execute only approved actions through Playwright.
- Record all outcomes in persistent memory.
- Continue discovering posts until the configured interaction limit or
  another stop condition is reached.

The core idea is:

```text
The browser observes.
The extractor structures.
The AI decides.
The validator controls.
The executor acts.
The database remembers.
```

---

# 2. Primary Objective

The project should make intelligent interaction decisions based on:

- A configured user profile.
- Interests and topics.
- Desired interaction style.
- Current interaction goal.
- Available posts.
- Previous interactions.
- Remaining interaction budget.

Example:

```text
User interests:
- Artificial Intelligence
- Startups
- Technology

Interaction goal:
- Build meaningful engagement

Maximum interactions:
- 10
```

The system may inspect many posts but interact with only the
highest-value posts.

---

# 3. The Fundamental Architecture

```text
                         ┌───────────────────┐
                         │   X / Twitter     │
                         │   Feed or Page    │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    PLAYWRIGHT     │
                         │ Browser Layer     │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ POST EXTRACTION   │
                         │ Read visible DOM  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ NORMALIZATION     │
                         │ Structured Posts  │
                         └─────────┬─────────┘
                                   │
                                   ▼
              ┌─────────────────────────────────────┐
              │           AI PLANNER                │
              │                                     │
              │ User Profile                        │
              │ Interaction Goal                    │
              │ Current Posts                       │
              │ Interaction History                 │
              │ Remaining Budget                    │
              └─────────────────┬───────────────────┘
                                │
                                ▼
                         ┌───────────────────┐
                         │ ACTION PLAN JSON  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ VALIDATION LAYER  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ PLAYWRIGHT        │
                         │ EXECUTOR          │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ MEMORY / DATABASE │
                         └─────────┬─────────┘
                                   │
                                   ▼
                           Scroll / Discover More
                                   │
                                   └───────────────► Repeat
```

This architecture must remain modular.

---

# 4. The Most Important Rule

## Never send raw page HTML directly to the AI unless there is a very specific, controlled reason.

The preferred pipeline is:

```text
Raw X Page
    ↓
Playwright DOM Access
    ↓
Post Extraction
    ↓
Structured JSON
    ↓
AI Planning
```

For example, this:

```json
{
  "post_id": "123",
  "author": "@example",
  "text": "AI agents will change software development.",
  "likes": 250,
  "replies": 42,
  "url": "..."
}
```

is much more useful than thousands of lines of browser HTML.

Benefits:

- Lower model context usage.
- Easier debugging.
- Cleaner AI prompts.
- Better validation.
- Stable internal interfaces.
- Easier testing.

---

# 5. System Components

The project contains seven major logical layers.

```text
1. Configuration
2. Browser
3. Extraction
4. Normalization
5. AI Planning
6. Validation + Execution
7. Memory + Observability
```

---

# 6. Layer 1 --- Configuration

Configuration defines how a run should behave.

Example:

```yaml
target:
  page: "https://x.com/home"

interaction:
  max_interactions: 10
  allowed_actions:
    - like
    - comment
    - reply

discovery:
  posts_per_batch: 30
  max_scroll_attempts: 10

runtime:
  max_retries: 2
  timeout_seconds: 1800
```

The configuration layer should also contain:

```text
USER_PROFILE
INTERACTION_GOAL
CONTENT_RESTRICTIONS
MAX_INTERACTIONS
MAX_POSTS_PER_BATCH
MAX_SCROLL_ATTEMPTS
MAX_RETRIES
RUN_TIMEOUT
```

Do not hardcode these values throughout the code.

---

# 7. Layer 2 --- Browser

## Technology

```text
Python
+
Playwright Async API
```

The browser layer owns:

- Browser startup.
- Context/session management.
- Navigation.
- Page access.
- Waiting for relevant page state.
- Scrolling.
- Locating posts.
- Performing approved interactions.

The browser layer does **not** decide:

- Which post is interesting.
- What should be commented.
- Whether a post aligns with the user's interests.

Those are planner responsibilities.

### Browser Architecture

```text
Browser Session
      │
      ▼
Navigation
      │
      ▼
Discover Posts
      │
      ▼
Extract Post Elements
      │
      ▼
Scroll
      │
      └────► Discover More
```

---

# 8. Layer 3 --- Post Extraction

The extractor converts browser elements into internal post objects.

## Required Conceptual Model

```text
Browser DOM Element
        ↓
Extract Fields
        ↓
Validate Identity
        ↓
Create Post Object
```

Suggested schema:

```json
{
  "post_id": "string",
  "url": "string",
  "author": {
    "name": "string",
    "username": "string"
  },
  "text": "string",
  "timestamp": "string | null",
  "likes": 0,
  "replies": 0,
  "reposts": 0,
  "is_reply": false,
  "is_repost": false
}
```

### Extraction Rules

The extractor should:

- Preserve original text.
- Extract stable identifiers.
- Normalize post URLs.
- Capture relevant metadata when available.
- Handle missing values.
- Never invent unavailable information.
- Avoid extracting unnecessary UI elements.

---

# 9. Layer 4 --- Normalization

The normalization layer prepares posts for planning.

```text
Extracted Posts
      │
      ▼
Clean Whitespace
      │
      ▼
Normalize URLs and Usernames
      │
      ▼
Remove Invalid Records
      │
      ▼
Deduplicate
      │
      ▼
Filter Previously Processed Posts
      │
      ▼
AI-Ready Post Batch
```

The output should be compact and deterministic.

Example:

```json
{
  "post_id": "123",
  "author_username": "@builder",
  "text": "Building AI agents is becoming easier.",
  "url": "https://...",
  "metadata": {
    "likes": 24,
    "replies": 5
  }
}
```

---

# 10. Layer 5 --- AI Planner

The AI is the **decision-making layer**, not the browser controller.

## Inputs

```text
User Profile
+
Interaction Goal
+
Eligible Posts
+
Previous Interaction History
+
Remaining Budget
+
Allowed Actions
+
Restrictions
```

## Planner Responsibilities

The planner determines:

1.  Which posts are relevant.
2.  Which posts should be skipped.
3.  Which interaction is appropriate.
4.  What text should be drafted for comments or replies.
5.  Which actions have the highest priority.

## Allowed Actions

Initial implementation:

```text
like
comment
reply
skip
```

The planner must not produce:

- Browser selectors.
- JavaScript commands.
- Playwright commands.
- Shell commands.
- Arbitrary tools.
- Unsupported action types.

---

# 11. Action Plan Contract

The AI must return structured data.

Example:

```json
{
  "actions": [
    {
      "post_id": "123",
      "action": "comment",
      "content": "Interesting perspective. The biggest shift may come when agents coordinate complete workflows rather than only assist individual tasks.",
      "reason": "Highly relevant to AI and technology interests.",
      "priority": 1
    },
    {
      "post_id": "456",
      "action": "like",
      "content": null,
      "reason": "Relevant but does not require a meaningful comment.",
      "priority": 2
    },
    {
      "post_id": "789",
      "action": "skip",
      "content": null,
      "reason": "Outside the current interaction goal.",
      "priority": 3
    }
  ]
}
```

The planner is allowed to recommend fewer actions than the maximum
budget.

It must never be forced to interact simply because budget remains.

---

# 12. Layer 6 --- Validation

Validation is the control boundary between AI reasoning and real browser
actions.

```text
AI Action Plan
      │
      ▼
Schema Validation
      │
      ▼
Action Allowlist
      │
      ▼
Post Identity Check
      │
      ▼
History Check
      │
      ▼
Budget Check
      │
      ▼
Content Validation
      │
      ▼
APPROVED ACTION
```

An action must be rejected if:

- Its schema is invalid.
- The action type is unsupported.
- The post is unknown.
- The post has already been interacted with.
- The budget is exhausted.
- Comment/reply content is missing.
- Content violates configured restrictions.

### Principle

```text
When uncertain:
Reject the action.
Do not guess.
```

---

# 13. Interaction Budget

A run may have:

```text
MAX_INTERACTIONS = 10
```

Example:

```text
Post A → Comment
Post B → Like
Post C → Skip
Post D → Reply
Post E → Like
```

Only valid executed interactions should count according to the
configured counting policy.

## Future Weighted Budget

Later, the project may support:

```text
Like    = 1 point
Comment = 2 points
Reply   = 2 points

Total budget = 15 points
```

However, the first implementation should use a simple count-based model.

---

# 14. Layer 7 --- Execution

The Playwright executor receives only validated actions.

```text
Validated Action
       │
       ▼
Locate Correct Post
       │
       ▼
Confirm Identity
       │
       ▼
Perform Action
       │
       ▼
Verify Result
       │
       ▼
Return Execution Result
```

Example:

```json
{
  "post_id": "123",
  "action": "comment",
  "status": "success",
  "timestamp": "2026-09-01T00:00:00Z",
  "error": null
}
```

Execution failures must be recorded.

Do not mark an action successful merely because an automation function
completed.

---

# 15. Interaction Memory

The system requires persistent memory.

## Suggested Record

```text
interaction_id
run_id
post_id
post_url
author_username
action
content
status
timestamp
error
```

Memory prevents:

- Duplicate interactions.
- Duplicate comments.
- Repeated actions caused by retries.
- Processing the same post repeatedly.

Memory also gives future planners context about recent activity.

---

# 16. Main Runtime Loop

This is the complete expected runtime.

```text
┌─────────────────────────┐
│ START RUN               │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Load Configuration      │
│ Load Interaction Memory │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Start Browser           │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Extract Visible Posts   │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Normalize + Deduplicate │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Remove Previous Posts   │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ AI Planner              │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Validate Action Plan    │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Execute Approved Actions│
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ Save Results            │
└────────────┬────────────┘
             ▼
      ┌───────────────┐
      │ Stop Condition│
      │ Reached?      │
      └───────┬───────┘
          YES │ NO
              │
        ┌─────▼─────┐
        │   STOP    │
        └───────────┘
              ▲
              │
      ┌───────┴───────┐
      │ Scroll / Find │
      │ New Posts     │
      └───────────────┘
```

---

# 17. Stop Conditions

A run stops when any configured stop condition is met.

Examples:

```text
1. Interaction budget reached.
2. Run timeout reached.
3. Maximum scroll attempts reached.
4. No meaningful new posts found repeatedly.
5. Critical browser failure.
6. Critical persistence failure.
7. Explicit user/system stop.
```

Example:

```text
Maximum interactions: 10

Successful actions: 10

→ STOP
```

---

# 18. Recommended Project Structure

```text
x_interaction_agent/
│
├── PROJECT.md
├── AGENTS.md
├── README.md
├── pyproject.toml
│
├── app/
│   │
│   ├── main.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── post.py
│   │   ├── action.py
│   │   ├── result.py
│   │   └── run_state.py
│   │
│   ├── browser/
│   │   ├── session.py
│   │   ├── navigator.py
│   │   ├── scraper.py
│   │   └── executor.py
│   │
│   ├── extraction/
│   │   ├── parser.py
│   │   ├── normalizer.py
│   │   └── deduplicator.py
│   │
│   ├── planner/
│   │   ├── planner.py
│   │   ├── prompts.py
│   │   └── schemas.py
│   │
│   ├── validation/
│   │   └── action_validator.py
│   │
│   ├── memory/
│   │   ├── repository.py
│   │   └── models.py
│   │
│   ├── services/
│   │   └── run_service.py
│   │
│   └── observability/
│       └── logging.py
│
└── tests/
    ├── test_normalizer.py
    ├── test_validator.py
    ├── test_memory.py
    └── test_runtime.py
```

---

# 19. Component Ownership

Component Responsibility

---

`browser/session.py` Browser and session lifecycle
`browser/navigator.py` Navigation and scrolling
`browser/scraper.py` Discover and extract post elements
`browser/executor.py` Execute approved browser interactions
`extraction/parser.py` Convert elements into post data
`extraction/normalizer.py` Clean and standardize data
`extraction/deduplicator.py` Remove duplicate posts
`planner/planner.py` Request and process AI decisions
`planner/prompts.py` Planner prompt construction
`validation/action_validator.py` Enforce deterministic rules
`memory/repository.py` Store and retrieve interaction history
`services/run_service.py` Orchestrate the complete run
`models/*` Shared typed contracts

No component should silently take ownership of another component's
responsibility.

---

# 20. Data Flow

```text
                  CONFIGURATION
                       │
                       ▼
┌──────────┐     ┌────────────┐
│ X Page   │────►│ PLAYWRIGHT │
└──────────┘     └─────┬──────┘
                      ▼
                ┌─────────────┐
                │ EXTRACTION  │
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │NORMALIZATION│
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │   PLANNER   │◄──── User Profile
                └──────┬──────┘◄──── Interaction Memory
                       ▼
                ┌─────────────┐
                │ ACTION PLAN │
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │ VALIDATOR   │
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │  EXECUTOR   │
                └──────┬──────┘
                       ▼
                ┌─────────────┐
                │   MEMORY    │
                └─────────────┘
```

---

# 21. AI Design Strategy

## Initial Version

Do not start with multiple autonomous agents.

Use:

```text
One Planner
+
Strict Structured Output
+
Deterministic Validation
+
Deterministic Execution
```

This is easier to:

- Debug.
- Test.
- Observe.
- Improve.
- Control.

## Future Expansion

The architecture may later evolve into:

```text
Content Relevance Agent
          +
Interaction Strategy Agent
          +
Comment Writer
          +
Safety / Validation Layer
```

But this should only happen after the basic single-planner system is
stable.

---

# 22. Suggested Technology Stack

## Core

```text
Python 3.11+
Playwright Async API
Pydantic
```

## Service Layer

Optional:

```text
FastAPI
```

Useful if the project later needs:

- API endpoints.
- Dashboard integration.
- Remote triggering.
- Multiple clients.

## Persistence

Recommended:

```text
PostgreSQL
```

For early local development:

```text
SQLite
```

## Optional Infrastructure

```text
Redis
```

Potential uses:

- Job state.
- Caching.
- Queues.
- Distributed execution.

Do not introduce infrastructure until it provides real value.

---

# 23. Error Strategy

The project should distinguish errors.

Suggested categories:

```text
BrowserError
ExtractionError
PlanningError
ValidationError
ExecutionError
PersistenceError
```

Example:

```text
Planner failure
→ Log error
→ Do not execute anything
→ End batch safely
```

Example:

```text
One post execution failure
→ Record failure
→ Respect retry policy
→ Continue with other eligible actions if appropriate
```

Never hide failures.

---

# 24. Observability

Every run should have a unique:

```text
run_id
```

Log important events:

```text
Run started
Browser started
Posts extracted
Posts normalized
Posts skipped from history
Planner called
Actions proposed
Actions rejected
Actions executed
Execution failures
Run completed
```

Useful metrics:

```text
posts_discovered
posts_eligible
posts_sent_to_planner
actions_proposed
actions_approved
actions_executed
actions_succeeded
actions_failed
interactions_remaining
scroll_count
run_duration
```

---

# 25. Testing Strategy

## Unit Tests

Test:

### Extraction / Normalization

- Empty posts.
- Missing fields.
- Duplicate IDs.
- Invalid URLs.
- Whitespace cleanup.

### Planner Output

- Invalid JSON handling.
- Unsupported action.
- Missing required content.

### Validation

- Budget enforcement.
- Duplicate prevention.
- Unknown post rejection.
- Invalid content rejection.

### Memory

- Successful interaction storage.
- Failed interaction storage.
- Duplicate lookup.

## Integration Tests

Test:

```text
Extract
→ Normalize
→ Plan
→ Validate
→ Mock Execute
→ Save Result
```

The budget must never be exceeded.

---

# 26. Implementation Roadmap

## Phase 1 --- Foundation

Deliverables:

- Repository structure.
- Configuration.
- Pydantic models.
- Logging.
- Basic tests.

## Phase 2 --- Browser Discovery

Deliverables:

- Playwright session.
- Navigation.
- Visible post discovery.
- Scrolling.

## Phase 3 --- Extraction

Deliverables:

- Post parser.
- Normalizer.
- Deduplicator.
- Structured post objects.

## Phase 4 --- Memory

Deliverables:

- Database schema.
- Interaction repository.
- Duplicate detection.

## Phase 5 --- Planner

Deliverables:

- User profile.
- Goal configuration.
- Planner prompt.
- Structured action schema.

## Phase 6 --- Validation

Deliverables:

- Schema validation.
- Budget checks.
- History checks.
- Content checks.

## Phase 7 --- Execution

Deliverables:

- Like action.
- Comment action.
- Reply action.
- Result verification.

## Phase 8 --- Full Runtime

Deliverables:

```text
Discover
→ Extract
→ Normalize
→ Plan
→ Validate
→ Execute
→ Remember
→ Scroll
→ Repeat
```

## Phase 9 --- Production Hardening

Deliverables:

- Better logging.
- Metrics.
- Recovery.
- Configuration profiles.
- Improved tests.

---

# 27. Definition of Done

The first complete version is finished when it can:

1.  Start a configured run.
2.  Open the target X page.
3.  Discover posts.
4.  Extract structured post data.
5.  Normalize and deduplicate the data.
6.  Load previous interaction history.
7.  Send eligible posts to the AI planner.
8.  Receive a strict action plan.
9.  Validate every action.
10. Execute only approved actions.
11. Verify and record outcomes.
12. Respect the maximum interaction budget.
13. Continue discovering posts when necessary.
14. Stop correctly when conditions are reached.

---

# 28. Final Project Principles

The project must always preserve:

## Principle 1 --- Separation of Concerns

```text
Browser ≠ AI
AI ≠ Validator
Validator ≠ Executor
Executor ≠ Memory
```

## Principle 2 --- Structured Boundaries

Important boundaries should use explicit schemas.

```text
Post
Action
ActionPlan
ExecutionResult
InteractionRecord
RunState
```

## Principle 3 --- AI Decides, Code Controls

```text
AI:
What should we do?

Validator:
Are we allowed to do it?

Executor:
How do we do it?

Memory:
What happened?
```

## Principle 4 --- Never Bypass Validation

```text
Planner Output
      ↓
Validation
      ↓
Execution
```

There must be no shortcut.

## Principle 5 --- Interaction Limits Are Absolute

The configured maximum interaction count must never be exceeded.

## Principle 6 --- Memory Prevents Repetition

Check history before planning and before execution.

---

# 29. The Complete Mental Model

The entire project can be remembered as:

```text
                 ┌─────────────┐
                 │   OBSERVE   │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │   EXTRACT   │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  NORMALIZE  │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │    PLAN     │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  VALIDATE   │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │   EXECUTE   │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │   VERIFY    │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  REMEMBER   │
                 └─────────────┘
                        │
                        ▼
                    DISCOVER MORE
```

# Final Statement

This project is an **AI-assisted interaction pipeline**, not an
uncontrolled browser bot.

Its intelligence comes from the planning layer.

Its reliability comes from:

- Structured data.
- Strict contracts.
- Validation.
- Interaction limits.
- Persistent memory.
- Verified execution.
- Modular architecture.

Every implementation decision should strengthen this pipeline:

```text
OBSERVE
→ EXTRACT
→ NORMALIZE
→ PLAN
→ VALIDATE
→ EXECUTE
→ VERIFY
→ REMEMBER
```

This is the permanent architectural backbone of the project.
