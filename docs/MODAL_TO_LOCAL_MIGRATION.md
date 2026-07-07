# Migration Guide: Modal Cloud → Local Sovereign Runner 🦁

## 1. Overview
This document outlines the architectural shift from a cloud-native serverless architecture (Modal) to a local, persistent hybrid architecture ("Sovereign Runner").

### Why the Move?
*   **Control**: Cloud functions are ephemeral and stateless. A local runner allows for persistent state (e.g., holding variables in memory between ticks).
*   **Latency**: Eliminates "cold start" times associated with spinning up cloud containers.
*   **Cost**: Leverages existing local hardware (Mac M-series) instead of paying per-second cloud compute costs for 24/7 scanning.
*   **Simplicity**: Debugging a local `while True` loop is vastly simpler than debugging distributed cloud logs.

## 2. Architecture Comparison

### Previous: Modal (Cloud) ☁️
*   **Execution**: Scheduled cron jobs (e.g., every 15 mins).
*   **State**: Stateless. Every run had to fetch all history from DB afresh.
*   **Logging**: CloudWatch/Modal Logs (Hard to tail in real-time).
*   **Alerts**: Webhook driven.

### Current: Local Sovereign Runner 🦁💻
*   **Execution**: A single `while True` loop running on your local machine (`src/runners/local_scanner.py`).
*   **State**: In-memory caching reducing API calls.
*   **Logging**: Direct stdout/terminal. Instant feedback.
*   **Database**: Still uses **Supabase** (Cloud Postgres) for persistent storage. The runner pushes data *out* to the cloud, but runs locally.

## 3. Key Components

### The Engine (`src/engines/smc_scanner.py`)
This remains the same. The core logic is portable. It runs inside the local runner just as it did in the cloud container.

### The Runner (`local_scanner.py`)
*   Replaces `modal_app.py`.
*   Connects to Supabase via `src/core/supabase_client.py`.
*   Handles the "Heartbeat" to let the dashboard know the system is alive.

### The Database (Supabase)
*   Remains the "Source of Truth".
*   If your local machine dies, the data is safe in the cloud.
*   When you restart the runner, it syncs with Supabase.

## 4. Operational Guide

### Starting the System
Instead of `modal deploy`, you now run:
```bash
./run
```
(Or directly: `venv/bin/python src/runners/local_scanner.py`)

### Stopping the System
```bash
Ctrl+C
```
(Or `kill` the python process).

### Maintenance
*   **Logs**: Check `local_runner.log` in the root (or just watch the terminal).
*   **Updates**: Pull latest code `git pull` and restart the runner.

## 5. Summary
We have moved "Compute" to the edge (your Mac) while keeping "Storage" in the cloud (Supabase). This offers the best of both worlds: Speed/Control of local + Reliability/Accessibility of cloud data.
