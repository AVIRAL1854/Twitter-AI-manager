# AGENTS.md --- X Interaction AI Agent

## 1. Project Purpose

This project is an AI-assisted interaction system for X (Twitter).

Its purpose is to:

1.  Use Playwright to navigate an X feed or target page.
2.  Extract visible posts and relevant metadata.
3.  Convert browser/DOM data into clean, structured post objects.
4.  Give structured posts, user preferences, goals, interaction history,
    and remaining interaction budget to an AI decision layer.
5.  Receive a strict structured action plan.
6.  Validate that plan before any browser action occurs.
7.  Use Playwright to execute only approved actions.
8.  Record every result in persistent interaction history.
9.  Continue discovering posts until the configured interaction limit or
    stop condition is reached.

The system is **not designed around sending raw page HTML to an LLM**.
Browser data must first be normalized into structured objects.

---

# 2. Core Architecture

The mandatory architecture is:

```text
X / Twitter
    ↓
Playwright Browser Layer
    ↓
Post Extraction Layer
    ↓
Normalization / Structured JSON
    ↓
AI Planning Layer
    ↓
Structured Action Plan
    ↓
Validation Layer
    ↓
Playwright Execution Layer
    ↓
Interaction Memory / Database
    ↓
Scroll / Discover More Posts
```

Keep these responsibilities separate. Do not merge browser automation,
AI reasoning, validation, and persistence into one large module.

---

# 3. Primary Design Principle

## The AI plans. The deterministic system executes.

The LLM must not directly perform arbitrary browser operations.

The AI may return:

- `like`
- `comment`
- `reply`
- `skip`

The executor decides **how** to perform the approved action through
Playwright.

Never allow free-form model output to become executable browser
commands.

---

# 4. Browser Layer

Use Python and Playwright, preferably the async API.

Responsibilities:

- Start and manage browser/context/session.
- Navigate to configured X pages.
- Discover visible posts.
- Scroll when more posts are required.
- Locate posts using stable identifiers where possible.
- Execute approved interactions.
- Verify whether an action succeeded.
- Return structured results.

The browser layer must not contain AI prompts or business-level decision
logic.

---

# 5. Post Extraction

Do not send complete raw HTML pages to the AI.

Extract each post into a normalized object.

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

Additional metadata may be added when reliably available.

Requirements:

- Every post must have a stable `post_id` or another unique key.
- Remove duplicate posts.
- Ignore browser/UI noise.
- Preserve the original post text.
- Handle missing metadata safely.
- Never invent extracted data.

---

# 6. Normalization Layer

The normalization layer converts extracted browser data into AI-ready
objects.

It should:

- Clean whitespace.
- Remove duplicate records.
- Normalize URLs.
- Normalize usernames.
- Handle missing values consistently.
- Filter posts that cannot be safely identified.
- Mark content type when useful.
- Keep the data compact enough for efficient model context.

Do not expose unnecessary DOM attributes to the planner.

---

# 7. AI Planning Layer

The planner receives:

```text
User Profile
+ Interaction Goals
+ Allowed Actions
+ Current Post Batch
+ Interaction History
+ Remaining Budget
+ Content Restrictions
```

The planner's responsibility is to decide:

1.  Which posts are relevant.
2.  Which posts should be skipped.
3.  Which action is appropriate.
4.  What comment or reply should be drafted when required.
5.  Which interactions have the highest priority.

The planner must return structured output only.

Example:

```json
{
  "actions": [
    {
      "post_id": "123",
      "action": "comment",
      "reason": "Highly relevant to the configured interests",
      "content": "Interesting perspective. The biggest shift may come when agents coordinate complete workflows rather than only assist individual tasks.",
      "priority": 1
    },
    {
      "post_id": "456",
      "action": "like",
      "reason": "Relevant content but no meaningful comment is needed",
      "content": null,
      "priority": 2
    },
    {
      "post_id": "789",
      "action": "skip",
      "reason": "Not relevant to current goals",
      "content": null,
      "priority": 3
    }
  ]
}
```

The planner must never output:

- Playwright code.
- CSS selectors.
- Arbitrary JavaScript.
- Shell commands.
- Instructions to bypass platform protections.
- Actions outside the configured allowlist.

---

# 8. Interaction Budget

Every run has a maximum interaction budget.

Example:

```text
MAX_INTERACTIONS = 10
```

Only successfully approved and executed interactions count toward the
budget unless configuration explicitly says otherwise.

Possible future weighted model:

```text
Like    = 1 point
Comment = 2 points
Reply   = 2 points
```

For the initial implementation, keep the budget logic simple and
deterministic.

The validator must guarantee:

```text
executed_interactions <= configured_limit
```

Never exceed the limit because of retries, scrolling, concurrency, or
duplicate planning.

---

# 9. Validation Layer

No AI action may reach the browser executor without validation.

Validate:

- Output schema.
- Valid action type.
- Post exists in the current known dataset.
- Post has not already been interacted with.
- Interaction budget remains.
- Required content exists for comments/replies.
- Content is non-empty when required.
- Content matches configured restrictions.
- Action is allowed by the current run configuration.

Invalid actions must be rejected and logged.

The validator should fail safely: reject the invalid action rather than
guessing.

---

# 10. Execution Layer

The executor receives only validated actions.

Example:

```python
await executor.execute(action)
```

The executor:

1.  Finds the intended post.
2.  Confirms its identity.
3.  Performs the approved action.
4.  Checks whether the operation succeeded.
5.  Returns a structured execution result.

Example result:

```json
{
  "post_id": "123",
  "action": "comment",
  "status": "success",
  "timestamp": "2026-09-01T00:00:00Z",
  "error": null
}
```

If execution fails:

- Do not blindly retry indefinitely.
- Record the failure.
- Respect retry limits.
- Do not exceed the interaction budget through retries.
- Continue or stop according to configured policy.

---

# 11. Interaction Memory

Persist interaction history.

Suggested fields:

```text
interaction_id
post_id
post_url
author_username
action
content
status
timestamp
run_id
error
```

Before planning or executing, check history.

At minimum, prevent:

- Repeating the same action on the same post.
- Reposting the same comment because of a retry.
- Accidentally interacting with duplicate extracted posts.

Interaction history is also useful for giving the planner context about
previous behavior.

---

# 12. Main Runtime Loop

The expected workflow is:

```text
START
  ↓
Initialize Run
  ↓
Load Configuration and Interaction History
  ↓
Open Browser
  ↓
Extract Visible Posts
  ↓
Normalize and Deduplicate
  ↓
Remove Previously Processed / Interacted Posts
  ↓
Send Eligible Batch to Planner
  ↓
Receive Structured Action Plan
  ↓
Validate Actions
  ↓
Execute Approved Actions
  ↓
Persist Results
  ↓
Interaction Limit Reached?
  ├── YES → STOP
  └── NO
         ↓
      Scroll / Discover More
         ↓
      Repeat
```

The loop must also stop when:

- No meaningful new posts are found after configured attempts.
- Browser/session cannot continue safely.
- A critical system error occurs.
- The configured run timeout is reached.

---

# 13. Project Structure

Recommended structure:

```text
project/
├── AGENTS.md
├── README.md
├── pyproject.toml
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── browser/
│   │   ├── session.py
│   │   ├── scraper.py
│   │   ├── navigator.py
│   │   └── executor.py
│   │
│   ├── extraction/
│   │   ├── parser.py
│   │   └── normalizer.py
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
│   └── models/
│       ├── post.py
│       ├── action.py
│       └── result.py
│
└── tests/
```

Avoid circular dependencies.

---

# 14. Coding Rules

When working on this repository:

## Do

- Use typed Python.
- Prefer Pydantic models for external/AI data boundaries.
- Keep functions focused.
- Use async Playwright APIs.
- Add structured logging.
- Make important limits configurable.
- Separate extraction, planning, validation, execution, and
  persistence.
- Handle failures explicitly.
- Write tests for critical validation and budgeting logic.
- Preserve deterministic behavior outside the AI planning layer.

## Do Not

- Put all logic into `main.py`.
- Send full raw HTML pages to the model.
- Allow the model to execute arbitrary browser commands.
- Trust AI output without validation.
- Hardcode interaction limits throughout the codebase.
- Use `sleep()` as the primary synchronization strategy when reliable
  Playwright waits are available.
- Assume every selector or page layout will remain stable.
- Treat failed actions as successful.
- Re-interact with posts without checking history.

---

# 15. Data Models

Prefer explicit models.

Example conceptual models:

```text
Post
Action
ActionPlan
ExecutionResult
InteractionRecord
RunState
```

`Action` should contain only supported fields.

Example:

```python
class Action:
    post_id: str
    action: Literal["like", "comment", "reply", "skip"]
    content: str | None
    reason: str
    priority: int
```

Keep the action contract strict.

---

# 16. Configuration

Configuration should include:

```text
MAX_INTERACTIONS
MAX_POSTS_PER_BATCH
MAX_SCROLL_ATTEMPTS
MAX_RETRIES
RUN_TIMEOUT
ALLOWED_ACTIONS
USER_PROFILE
INTERACTION_GOAL
CONTENT_RESTRICTIONS
```

Do not scatter configuration values across modules.

---

# 17. Error Handling

Use explicit error categories where useful:

```text
BrowserError
ExtractionError
PlanningError
ValidationError
ExecutionError
PersistenceError
```

Log enough context to debug failures without storing unnecessary
sensitive data.

A single failed post should generally not crash the entire run unless
the failure is critical.

---

# 18. Testing Priorities

At minimum, test:

### Normalization

- Duplicate removal.
- Missing metadata.
- Invalid URLs.
- Empty text.

### Validation

- Invalid actions rejected.
- Unknown posts rejected.
- Budget cannot be exceeded.
- Comments require content.
- Duplicate interactions rejected.

### Memory

- Previous interactions are detected.
- Failed and successful actions are correctly recorded.

### Runtime

- Run stops at maximum interactions.
- Run stops after repeated empty discovery cycles.
- Failed execution does not incorrectly increment successful
  interaction count.

---

# 19. Development Order

Build in this order:

## Phase 1 --- Foundation

- Project structure.
- Configuration.
- Pydantic models.
- Logging.
- Database/repository interface.

## Phase 2 --- Browser Extraction

- Playwright session.
- Post discovery.
- Post extraction.
- Normalization.
- Deduplication.

## Phase 3 --- Planning

- User profile schema.
- Planner interface.
- Strict action output schema.
- Action ranking.

## Phase 4 --- Validation

- Budget enforcement.
- Duplicate prevention.
- Content validation.
- Action allowlist.

## Phase 5 --- Execution

- Like executor.
- Comment executor.
- Reply executor.
- Success verification.
- Failure handling.

## Phase 6 --- Runtime Loop

- Batch processing.
- Scroll logic.
- Stop conditions.
- Persistence.
- End-to-end tests.

Do not begin with a complex autonomous multi-agent framework. A single
planner with strict tool boundaries is the preferred first
implementation.

---

# 20. Definition of Done

A working version should be able to:

1.  Open the configured target X page.
2.  Extract a batch of identifiable posts.
3.  Normalize them into structured objects.
4.  Remove duplicates and previously processed posts.
5.  Ask the planner for a structured action plan.
6.  Validate every proposed action.
7.  Execute only approved actions.
8.  Never exceed the configured interaction limit.
9.  Record all outcomes.
10. Continue discovering posts until a stop condition is reached.

The system should be understandable, modular, testable, and safe to
debug.

---

# 21. Final Rule for Coding Agents

Whenever making an architectural decision, preserve this chain:

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

Do not bypass steps.

The goal is not to create the most autonomous system possible. The goal
is to create a reliable system where AI reasoning is used for
**decision-making**, while deterministic code remains responsible for
**validation, browser execution, limits, and state**.
