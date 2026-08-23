"""
Sovereign Swarm Telemetry & Observability Engine
================================================
Lightweight, zero-latency, asynchronous telemetry tracing for the 7-Agent DMACP swarm.
Captures agent execution latency, prompt reasoning, state transitions, and causal verdicts
in a non-blocking background thread without adding a single millisecond to live order routing.
"""

import time
import json
import logging
import threading
from queue import Queue, Empty
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from src.core.config import Config
from src.core.database import get_db_connection

logger = logging.getLogger(__name__)

@dataclass
class AgentStepRecord:
    agent_name: str
    stage: str
    latency_ms: float
    status: str  # 'PASSED', 'FAILED', 'BLOCKED', 'OVERRIDDEN'
    input_summary: Dict[str, Any] = field(default_factory=dict)
    output_summary: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class SwarmTrace:
    trace_id: str
    symbol: str
    direction: str
    prompt_version: str = "v2.4.0-DMACP"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration_ms: float = 0.0
    final_verdict: str = "PENDING"
    ai_score: float = 0.0
    steps: List[AgentStepRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(
        self,
        agent_name: str,
        stage: str,
        latency_ms: float,
        status: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None
    ):
        step = AgentStepRecord(
            agent_name=agent_name,
            stage=stage,
            latency_ms=round(latency_ms, 2),
            status=status,
            input_summary=input_data or {},
            output_summary=output_data or {},
            reasoning=reasoning
        )
        self.steps.append(step)

    def finalize(self, final_verdict: str, ai_score: float, metadata: Optional[Dict[str, Any]] = None):
        self.end_time = time.time()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)
        self.final_verdict = final_verdict
        self.ai_score = ai_score
        if metadata:
            self.metadata.update(metadata)


class SwarmTelemetryManager:
    """
    Singleton Asynchronous Telemetry Collector.
    Spawns a lightweight background worker daemon to persist agent traces
    to local SQLite and Supabase with zero impact on trading latency.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SwarmTelemetryManager, cls).__new__(cls)
                cls._instance._init_worker()
            return cls._instance

    def _init_worker(self):
        self._queue = Queue(maxsize=1000)
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True, name="SwarmTelemetryWorker")
        self._worker_thread.start()
        self._init_db_table()
        logger.info("⚡ Swarm Telemetry Manager initialized (Async Background Worker Active).")

    def _init_db_table(self):
        try:
            conn = get_db_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS swarm_telemetry_traces (
                    trace_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    direction TEXT,
                    prompt_version TEXT,
                    total_duration_ms REAL,
                    final_verdict TEXT,
                    ai_score REAL,
                    steps_count INTEGER,
                    trace_payload TEXT
                );
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Telemetry DB init warning: {e}")

    def create_trace(self, symbol: str, direction: str, prompt_version: str = "v2.4.0-DMACP") -> SwarmTrace:
        trace_id = f"trace_{int(time.time()*1000)}_{symbol.replace('/', '')}_{direction}"
        return SwarmTrace(trace_id=trace_id, symbol=symbol, direction=direction, prompt_version=prompt_version)

    def log_trace_async(self, trace: SwarmTrace):
        """Pushes finalized trace to background queue (Non-blocking: <0.1ms)."""
        try:
            self._queue.put_nowait(trace)
        except Exception as e:
            logger.warning(f"Telemetry queue full, dropping trace: {e}")

    def _process_queue(self):
        """Background worker thread processing telemetry persistence."""
        while True:
            try:
                trace: SwarmTrace = self._queue.get(timeout=2.0)
                self._persist_trace(trace)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in telemetry background worker: {e}")

    def _persist_trace(self, trace: SwarmTrace):
        try:
            payload_dict = asdict(trace)
            payload_json = json.dumps(payload_dict)
            now_iso = datetime.now(timezone.utc).isoformat()

            conn = get_db_connection()
            conn.execute("""
                INSERT OR REPLACE INTO swarm_telemetry_traces (
                    trace_id, timestamp, symbol, direction, prompt_version,
                    total_duration_ms, final_verdict, ai_score, steps_count, trace_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trace.trace_id, now_iso, trace.symbol, trace.direction,
                trace.prompt_version, trace.total_duration_ms,
                trace.final_verdict, trace.ai_score, len(trace.steps), payload_json
            ))
            conn.commit()
            conn.close()
            logger.info(f"📊 Swarm Telemetry logged: {trace.trace_id} ({trace.total_duration_ms}ms, {len(trace.steps)} steps, Verdict: {trace.final_verdict})")
        except Exception as e:
            logger.error(f"Failed to persist swarm telemetry trace: {e}")

# Global Telemetry Instance
telemetry = SwarmTelemetryManager()
