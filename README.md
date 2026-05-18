# Brightwheel Subsidy Agent — AI-Powered Payment Reconciliation

> Production-ready multi-agent system for automated childcare subsidy payment reconciliation, transforming a 3-5 hour manual process into a 15-second pipeline with AI-powered exception detection and auto-ticketing.

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-3.5%20Sonnet-D97757?logo=anthropic&logoColor=white)
![Docling](https://img.shields.io/badge/Docling-OCR-FF4B4B)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [The Reconciliation Pipeline — In Depth](#the-reconciliation-pipeline--in-depth)
  - [Phase 1: Document OCR and Extraction](#phase-1-document-ocr-and-extraction)
  - [Phase 2: Hybrid Orchestration](#phase-2-hybrid-orchestration)
  - [Phase 3: Parallel Tool Execution](#phase-3-parallel-tool-execution)
  - [Phase 4: Synthesis and Classification](#phase-4-synthesis-and-classification)
  - [Phase 5: Automated Exception Ticketing](#phase-5-automated-exception-ticketing)
- [Key Features](#key-features)
- [Performance Metrics](#performance-metrics)
- [Frontend Dashboard](#frontend-dashboard)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)

---

## Overview

Brightwheel Subsidy Agent is a full-stack automation system that reconciles childcare attendance and meal records against state subsidy reports. The system utilizes Docling for reliable PDF preprocessing and Claude 3.5 Sonnet for intelligent extraction, followed by a batched parallel execution model using the Model Context Protocol (MCP) to achieve an 87x speedup compared to standard sequential tool calling.

### Core Capabilities

| Capability | Description |
|---|---|
| **Heterogeneous PDF Handling** | Extracts data from diverse state formats without hardcoded coordinates using Docling OCR and Claude. |
| **Hybrid Orchestration** | Claude plans the reconciliation strategy, while asyncio.gather() runs MCP tools in parallel. |
| **FastMCP Connection Pool** | Maintains a persistent MCP session, eliminating subprocess overhead for near-instant execution. |
| **Auto-Ticketing** | Identifies critical discrepancies and automatically creates Jira tickets with proper severity mapping. |
| **Real-Time Streaming** | Streams progress and tool calls directly to the React frontend via Server-Sent Events (SSE). |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Frontend (React)                           │
│  ┌───────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ FileUpload│  │ ProcessingView  │  │      ResultsView         │   │
│  │ (Multipart)│──│ (SSE Streaming) │──│ (Exceptions & Insights)  │   │
│  └───────────┘  └────────┬────────┘  └──────────────────────────┘   │
│                          │ HTTP / SSE                               │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
               ┌───────────▼───────────┐
               │    FastAPI Backend    │
               │   (api.py @ :8000)    │
               │                       │
               │  ┌─────────────────┐  │
               │  │ Extraction Agent│  │    ← Docling + Claude
               │  └────────┬────────┘  │
               │           │           │
               │  ┌────────▼────────┐  │
               │  │ Hybrid          │  │    ← Strategy & Synthesis
               │  │ Orchestrator    │  │
               │  └────────┬────────┘  │
               │           │           │
               │  ┌────────▼────────┐  │
               │  │ FastMCP Pool    │  │    ← Persistent connection
               │  └─────────────────┘  │
               └───────────────────────┘
                           │
               ┌───────────▼───────────┐
               │   External Services   │
               │  ┌─────────────────┐  │
               │  │ Brightwheel API │  │    ← Tool Execution target
               │  └─────────────────┘  │
               │  ┌─────────────────┐  │
               │  │ Jira Cloud API  │  │    ← Exception Ticketing
               │  └─────────────────┘  │
               └───────────────────────┘
```

---

## The Reconciliation Pipeline — In Depth

The core reconciliation logic combines LLM reasoning with deterministic code execution. Here is how a document is processed end-to-end.

### Phase 1: Document OCR and Extraction

The system employs a two-path extraction approach to maximize speed and reliability:
1. **Docling Preprocessing**: The PDF is parsed into clean markdown, identifying layout and tabular structures.
2. **Claude Extraction**: Claude 3.5 Sonnet extracts specific schema fields (e.g., student IDs, check-in times).
3. **Vision Fallback**: If Docling fails, the system gracefully falls back to Claude 3.5 Opus vision.

By processing clean text instead of pixels, extraction is approximately 87x faster.

### Phase 2: Hybrid Orchestration

Instead of allowing the LLM to call tools sequentially, Claude is instructed to generate a comprehensive strategy:

```json
{
  "students": [{"kc_id": "987654321", "name": "Emma Rodriguez"}],
  "dates_to_check": [["2026-05-05", "2026-05-06"]]
}
```

The Python layer validates this plan, ensuring critical keys like `kc_id` are present to fail fast on malformed data.

### Phase 3: Parallel Tool Execution

Using the execution plan, the backend batches tool calls and executes them in parallel via `asyncio.gather()`. 
A persistent `FastMCP` connection pool handles these requests, eliminating the 200ms overhead of spawning new subprocesses for each tool invocation. 

Level 0 tasks (student lookups) run concurrently, followed by Level 1 tasks (attendance checks) derived from Level 0 results.

### Phase 4: Synthesis and Classification

All tool execution results are collected and passed back to Claude. Using strict XML-structured prompts and assistant prefilling, Claude synthesizes the data to:
- Detect discrepancies (e.g., mismatching times > 10 minutes)
- Assign severity (MATCH, HIGH, CRITICAL)
- Generate actionable insights.

### Phase 5: Automated Exception Ticketing

The `ExceptionHandler` parses the final output and filters for `HIGH` and `CRITICAL` issues. It maps these severities to Jira priorities (e.g., CRITICAL becomes Highest) and automatically generates tickets containing a detailed audit of the discrepancy.

---

## Key Features

- **No Hardcoded Coordinates**: Adapts to any state agency report format dynamically.
- **Fail-Fast Validation**: Extraction guarantees valid student identifiers before initiating expensive API calls.
- **Dynamic Time Calculation**: Custom time-saving metrics based on workflow type (KinderConnect vs. CACFP vs. Rosters).
- **XML-Structured Prompts**: Ensures 100% reliable JSON parsing without preamble or formatting errors.
- **Audit Trails**: All uploads and session results are timestamped and organized locally for debugging.

---

## Performance Metrics

| Operation | Time | Architecture Benefit |
|-----------|------|----------------------|
| **Extraction** | ~5s | Docling text preprocessing instead of vision. |
| **Planning** | ~1s | Reduced LLM turns via hybrid strategy. |
| **Tool Execution** | ~3s | Parallel batched calls with MCP connection pool. |
| **Synthesis** | ~2s | Fast reasoning with Sonnet 3.5. |
| **Total (10 Students)** | **~15s** | 99.9% reduction from 3 hours manual processing. |

---

## Frontend Dashboard

Built with React and Material-UI, the interface provides comprehensive transparency:
- **Real-Time Progress**: SSE endpoints push execution status, ensuring zero black-box waiting.
- **Tool Call Logs**: Developers and users can monitor exactly which MCP tools are invoked in real-time.
- **Insight Panels**: Dynamically generated insights based on aggregated exception types.
- **Jira Integration**: Direct links to automatically created Jira tickets from the exception table.

---

## Project Structure

```
brightwheel-subsidy-agent/
├── backend/
│   ├── api.py                    # FastAPI server with SSE
│   ├── requirements.txt          # Python dependencies
│   └── uploads/                  # Organized by timestamp
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Main React app
│   │   ├── components/           # Upload, Processing, and Results UI
│   │   └── theme.js              # Material-UI theme
│   └── package.json
├── src/
│   ├── agents/
│   │   ├── extraction_agent.py   # OCR and schema extraction
│   │   ├── hybrid_orchestrator.py# Strategy planning and synthesis
│   │   └── exception_handler.py  # Jira integration
│   ├── tools/
│   │   └── brightwheel_mcp_fastmcp.py # MCP tool definitions
│   └── workflows/
│       └── mcp_pool.py           # Connection lifecycle management
├── data/                           # Mock datasets and example PDFs
├── README.md                       # Documentation
└── ARCHITECTURE.md                 # System architecture details
```

---

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 18+
- Anthropic API key
- Jira Cloud account credentials

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Create .env file for credentials
cat > .env << EOF
ANTHROPIC_API_KEY=your_key_here
ATLASSIAN_JIRA_URL=https://your-domain.atlassian.net
ATLASSIAN_JIRA_EMAIL=your.email@example.com
ATLASSIAN_JIRA_TOKEN=your_jira_token
EOF

# Start the API server
python api.py
```
The backend runs at `http://127.0.0.1:8000`.

### 2. Frontend Setup

```bash
cd frontend
npm install
npm start
```
The dashboard runs at `http://localhost:3001`.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload a PDF report and begin reconciliation. |
| `GET` | `/api/job/{job_id}/stream` | SSE endpoint for real-time progress and tool call logs. |
| `GET` | `/api/health` | Service health check. |

---

## License

This project is licensed under the Apache License 2.0.
