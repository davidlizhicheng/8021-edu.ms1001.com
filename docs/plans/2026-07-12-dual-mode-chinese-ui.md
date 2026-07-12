# Dual-mode Chinese UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the mixed-language tool portal with a Chinese-only student/teacher workbench organized around the real wrong-answer workflow.

**Architecture:** Add a focused mode-aware dashboard and navigation layer while preserving existing view IDs and API bindings. Use CSS visibility and small JS routing helpers to keep mature features available without duplicating business logic.

**Tech Stack:** Vanilla HTML, CSS and JavaScript.

---

1. Add student/teacher mode state, Chinese labels and mode-aware navigation.
2. Build focused student and teacher dashboards with live counts.
3. Reposition full-paper and single-question workbenches behind clear task actions.
4. Replace mixed-language labels and remove decorative English copy.
5. Add responsive desktop sidebar and mobile bottom navigation.
6. Verify syntax, views, both modes, production health and publish with backup.
