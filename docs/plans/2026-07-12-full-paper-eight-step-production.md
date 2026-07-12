# Full-paper Eight-step Production Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver production full-paper extraction, handwriting-aware grading, fixed eight-step wrong-answer analysis, durable history, Word/PDF export, and safe unified-account billing integration.

**Architecture:** Add paper/job/question tables beside the existing single-question tables and reuse the current diagnosis, variant, mastery, and archive pipeline per extracted wrong question. Full-paper processing is a resumable background job; every page and question has a stable record, confidence, review state, and source reference. Exports are generated from stored normalized results so they can be reproduced without rerunning models.

**Tech Stack:** Python 3 standard library HTTP server, SQLite, pypdf, python-docx, reportlab, vanilla JavaScript/CSS, Docker/PM2 production deployment.

---

### Task 1: Pure paper and eight-step domain rules
- Create `paper_workflow.py` and `test_paper_workflow.py`.
- Test question segmentation, grading-state normalization, wrong-question filtering, eight-step normalization, progress and export-safe data.
- Implement minimal pure functions and run unit tests.

### Task 2: Backward-compatible persistence and job API
- Modify `server.py` to add `exam_papers`, `paper_pages`, `paper_questions`, and `paper_jobs`.
- Add create/list/detail/retry APIs with user ownership checks.
- Process jobs in a bounded background thread and persist progress/errors.
- Reuse `wrong_questions` for every wrong or partially correct paper question.

### Task 3: OCR, handwriting and eight-step model contracts
- Add full-paper OCR prompt returning page/question coordinates, printed content, handwriting, marks, score and confidence.
- Add fixed eight-step prompt/output for each wrong question.
- Require calibration for low-confidence segmentation or handwriting.
- Preserve original OCR evidence and model output for audit.

### Task 4: Full-paper workbench and history
- Modify `web/index.html`, `web/app.js`, and `web/styles.css`.
- Add upload/progress/result/history views with per-question correction.
- Display correct, wrong, partial, blank and review-required states.
- Link extracted wrong questions to the existing mastery and spaced-review flow.

### Task 5: Word/PDF export and unified billing
- Generate reproducible DOCX and PDF paper reports.
- Add download endpoints and history entries.
- Attempt central billing through the configured ai.ms1001.com endpoint with idempotency keys; retain local fallback only when configured.

### Task 6: Production verification and release
- Run unit, syntax, migration, API and export tests.
- Back up the production database and uploads.
- Upload changed files without replacing `.env`, `data`, uploads, cards or exports.
- Restart the production process and verify health, homepage, unified auth, paper APIs and downloads.
- Roll back from the timestamped release directory if any production check fails.
