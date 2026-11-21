# LatchOS API — Automated Compliance Verification & Cyber-Physical Access Control

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**LatchOS** is a backend verification and cyber-physical access control engine built with **FastAPI**, **PostgreSQL**, and **multi-model LLM orchestration (Claude & Gemini)**. It automates unstructured compliance document verification and enforces deterministic, auditable gate barrier access decisions.

---

## System Architecture

```text
[Driver / Gate Terminal]
         │
         ▼ (TLS + Role-Based Auth / Session Token)
┌────────────────────────────────────────────────────────┐
│                 FastAPI Gateway Layer                   │
│  • Input Sanitization & Schema Validation (Pydantic)   │
│  • Role-Based Access Control (RBAC) & Rate Limiting    │
└────────────────────────┬───────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌──────────────────────┐       ┌─────────────────────────┐
│ Multi-Model LLM      │       │ PostgreSQL Audit &      │
│ Verification Router  │       │ Policy State Store      │
│ • Claude / Gemini    │       │ • Immutable Access Logs │
│ • Structured JSON    │       │ • Compliance Rulesets   │
│   Extraction & Guard │       │ • Expiry & Revocation   │
└──────────┬───────────┘       └────────────┬────────────┘
           │                                │
           └───────────────┬────────────────┘
                           ▼
             [Deterministic Policy Engine]
             (Fail-Closed Gate Actuation)
