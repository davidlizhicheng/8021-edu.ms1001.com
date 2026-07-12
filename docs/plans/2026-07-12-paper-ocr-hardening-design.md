# Paper OCR Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make full-paper recognition preserve usable OCR results, reduce malformed-response failures, avoid unnecessary duplicate model calls, and deploy the verified change to edu.ms1001.com.

**Architecture:** Keep the configured vision provider as the primary recognizer, but move response normalization and repair into a deterministic local pipeline. Validate OCR payloads before persistence, recover text from malformed JSON when possible, and retry only when a quality gate says the first result is unusable. Preserve production data and model configuration during deployment.

**Tech Stack:** Python 3, SQLite, HTTP vision-model API, unittest, existing Paramiko deployment tooling.

---

### Task 1: Add malformed OCR response regression tests

**Files:**
- Create: `tests/test_ocr_resilience.py`
- Modify: `server.py`

**Steps:**
1. Add failing tests for fenced JSON, trailing commas, unescaped control characters, truncated question arrays, and plain OCR text.
2. Assert that recoverable responses return a valid OCR envelope instead of raising `JSONDecodeError`.
3. Run `python -m unittest tests.test_ocr_resilience -v` and confirm the new cases initially fail.

### Task 2: Implement deterministic response recovery and validation

**Files:**
- Modify: `server.py`
- Test: `tests/test_ocr_resilience.py`

**Steps:**
1. Add a conservative JSON cleaning and decoding sequence.
2. Add an OCR-specific fallback that preserves `page_text` and extracts numbered questions from model text.
3. Normalize question fields, confidence values, answer states, and bounding boxes.
4. Return repair metadata for observability without exposing model secrets.
5. Run the focused tests and confirm all recovery cases pass.

### Task 3: Improve speed with a quality-gated retry policy

**Files:**
- Modify: `server.py`
- Test: `tests/test_ocr_resilience.py`

**Steps:**
1. Replace the broad confidence-only retry trigger with explicit unusable-result checks.
2. Skip a second model call when printed text and question segmentation are already usable.
3. Retry once only for empty output, malformed fallback output, very low confidence, or implausible question segmentation.
4. Add tests proving good results call the recognizer once and poor results at most twice.

### Task 4: Add lightweight image normalization

**Files:**
- Modify: `server.py`
- Modify: `requirements.txt`
- Test: `tests/test_ocr_resilience.py`

**Steps:**
1. Decode uploaded raster images safely and apply EXIF orientation.
2. Downscale oversized pages to the model's useful resolution while preserving aspect ratio and JPEG quality.
3. Avoid automatic content rotation unless orientation evidence is reliable.
4. Fall back to the original data URL when preprocessing is unavailable or fails.
5. Verify normalized images are smaller and still valid image data.

### Task 5: Run local quality and performance regression

**Files:**
- Use: the four supplied JPG fixtures outside the repository

**Steps:**
1. Run the complete unit-test suite.
2. Run all four sample pages through the updated OCR entry point.
3. Record structured success, extracted question count, repair status, recognition attempts, and elapsed time.
4. Compare against the baseline captured on 2026-07-12.

### Task 6: Deploy safely and verify production

**Files:**
- Use: `deploy/scripts/deploy-edu-full-paper.py`

**Steps:**
1. Inspect the deployment script to confirm it excludes `.env`, the SQLite database, uploads, cards, and exports.
2. Back up the current remote application code or use the script's backup behavior.
3. Upload only the tested code and dependency changes.
4. Restart the existing edu service without replacing production data.
5. Verify the health endpoint, public HTTPS response, and one authenticated or safe OCR smoke path.
6. If verification fails, restore the pre-deployment version and restart the service.
