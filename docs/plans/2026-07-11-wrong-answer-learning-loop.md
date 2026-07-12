# Wrong-answer Learning Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the wrong-answer product from a one-time three-question pass flow into a calibrated, diagnosed, adaptive, spaced-review mastery loop.

**Architecture:** Keep the existing Python/SQLite/vanilla-JS application and add a pure workflow module for mastery scoring, review scheduling, and state transitions. Persist workflow state on `wrong_questions`, expose it through existing endpoints, and preserve compatibility with old rows and the existing `passed` status.

**Tech Stack:** Python 3, SQLite, standard-library HTTP server, vanilla JavaScript, CSS.

---

### Task 1: Add workflow rules with tests

**Files:**
- Create: `learning_workflow.py`
- Create: `test_learning_workflow.py`

1. Write tests for OCR confidence gating, error taxonomy normalization, three-level practice labels, mastery scoring, retry transitions, and 1/3/7/14/30-day scheduling.
2. Run the tests and confirm they fail before implementation.
3. Implement the pure workflow functions.
4. Run the tests and confirm they pass.

### Task 2: Persist workflow state

**Files:**
- Modify: `server.py`

1. Add backward-compatible SQLite columns for error type, mastery score, review stage, next review time, last review time, and workflow state.
2. Enrich diagnosis records with normalized error diagnosis and tiered practice metadata.
3. Replace the one-shot pass update with the workflow transition calculation.
4. Return workflow state through existing wrong-question APIs.
5. Add a due-review endpoint and verify it with an isolated temporary database.

### Task 3: Connect the student workflow

**Files:**
- Modify: `web/app.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`

1. Show calibration, diagnosis, tier, mastery, and next-review status using existing components.
2. On a wrong answer, present a minimal hint and keep the item in remediation instead of exposing completion.
3. Include due reviews in Today’s Tasks and support mastered/review-due states.
4. Verify the full browser flow at desktop and mobile widths.

### Task 4: Clean personal demo content and align agent badges

**Files:**
- Modify: `3000-ai.ms1001.com/web/portal_app.js`
- Modify: `8075-events.ms1001.com/data/records.json`
- Modify: `8107-teaching.ms1001.com/app.js`
- Modify: `_shared/ms1001-ui/ms1001-sites-registry.js`
- Modify: `3000-ai.ms1001.com/web/shared/ms1001-sites-registry.js`

1. Remove the developer credit and the event/course records associated with the named person.
2. Derive the canonical two-character badge mapping from the portal’s listed agent order/domain mapping.
3. Apply the mapping to both shared registries and verify there are no divergent copies.

### Task 5: Fix theme contrast defects only

**Files:**
- Modify: `8105-selftest.ms1001.com/frontend/中国企业连锁品牌测评与复盘.html`
- Modify only other directly implicated theme styles if reproduced.

1. Add explicit light/dark semantic colors for text, controls, borders, and progress marks.
2. Verify the questionnaire in both themes and confirm no light-on-light or dark-on-dark content remains.

### Task 6: Final verification

1. Run workflow unit tests.
2. Run Python syntax compilation and JavaScript syntax checks for modified files.
3. Search production source paths for the removed personal content.
4. Compare shared registry badge mappings.
5. Capture and inspect screenshots of the corrected questionnaire and upgraded wrong-answer workflow.
