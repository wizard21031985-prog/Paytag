# logger/logger_service.py
import sys
from datetime import datetime
from queue import Queue
from database.db_actions import DbAction


class PayTagLogger:
    def __init__(self, config: dict, db_queue: Queue):
        self.config = config
        self.db_queue = db_queue  # The thread-safe pipeline to the DB background worker
        self.min_level = config['database']['min_log_level'].upper()

        # Severity hierarchy weight mapping
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}

    def _should_log(self, severity: str) -> bool:
        """Filters log requests based on the configured min_log_level threshold."""
        return self.levels.get(severity, 1) >= self.levels.get(self.min_level, 2)

    def log_system_event(self, severity: str, message: str, transaction_number: str = None,
                         hardware_fault: dict = None, code_exception: str = None, technical_details: dict = None):
        """
        Public decoupled interface for logging application and infrastructure events.
        Pushes payloads to the non-blocking database ingestion thread instantly (0ms).
        """
        severity = severity.upper()
        if not self._should_log(severity):
            return

        # 1. Structure the standardized technical data payload
        log_payload = {
            "timestamp": datetime.utcnow(),
            "severity": severity,
            "message": message,
            "transaction_number": transaction_number,
            "hardware_fault": hardware_fault,
            "code_exception": code_exception,
            "technical_details": technical_details
        }

        # 2. Real-time Console output (Immediate visual feedback for the local operator)
        output_stream = sys.stderr if severity in ["ERROR", "CRITICAL"] else sys.stdout
        output_stream.write(f"[{log_payload['timestamp'].isoformat()}] [{severity}] {message}\n")
        output_stream.flush()

        # 3. Stream data asynchronously onto the queue conveyor belt via type-safe DbAction Enum
        db_message = {
            "action": DbAction.INSERT_LOG,
            "payload": log_payload
        }
        self.db_queue.put(db_message)

    def log_hardware_heartbeat(self, simulator_version: str, reader_connected: bool,
                               neutralizer_connected: bool, all_connected: bool,
                               is_reachable: bool, response_time_ms: int):
        """
        Asynchronously routes background hardware telemetry snapshots directly to the
        health_checks database worker loop at 0ms latency.
        """
        heartbeat_payload = {
            "timestamp": datetime.utcnow(),
            "simulator_version": simulator_version,
            "hardware_status": {
                "reader_connected": reader_connected,
                "neutralizer_connected": neutralizer_connected,
                "all_connected": all_connected
            },
            "connectivity": {
                "is_simulator_reachable": is_reachable,
                "response_time_ms": response_time_ms
            }
        }

        db_message = {
            "action": DbAction.INSERT_HEARTBEAT,
            "payload": heartbeat_payload
        }
        self.db_queue.put(db_message)
