# Online Text Quality Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate user-visible mojibake and unhelpful "未返回" placeholders from the production wrong-question experience.

**Architecture:** Repair legacy UTF-8-as-CP1252 strings recursively at the server boundary, then normalize every diagnosis into a complete Chinese schema before returning or persisting it. Keep a small frontend safety layer for dynamic rendering and migrate existing database JSON after backup. Add automated and production smoke gates that fail on known mojibake signatures or missing core fields.

**Tech Stack:** Python 3, SQLite, browser JavaScript, unittest, existing SSH deployment tooling.

---

### Task 1: Text repair and detection
- Add tests covering common mojibake sequences and nested JSON values.
- Implement conservative CP1252/UTF-8 repair with confidence checks.
- Add a detector for replacement characters, mojibake signatures and control characters.

### Task 2: Complete diagnosis contracts
- Add tests requiring useful Chinese defaults for core pattern, goal, decomposition, standard answer and student guidance.
- Normalize newly generated, fallback and historical diagnoses through one function.
- Remove all frontend "未返回" placeholders and replace them with actionable content.

### Task 3: Existing data migration
- Back up the production SQLite database.
- Recursively repair diagnosis JSON, variants and visible profile fields.
- Normalize missing diagnosis fields without inventing authoritative answers.

### Task 4: Deployment and production gates
- Run focused tests, full tests, Python compilation and JavaScript syntax checks.
- Deploy with the existing automatic code backup.
- Verify health, live asset version and latest wrong-question API payloads.
- Fail the release if mojibake signatures, "未返回" strings or empty required fields remain.
