# PayTag POS Client - Architecture & Design Plan

This document outlines the software design, collection schemas, error-handling strategy, and structural architectural choices made prior to implementing the PayTag self-checkout client integration.

---

## 1. Database Architecture (MongoDB)
Technical logging and operational business data layers are split across two isolated databases using explicit, indexed schemas. This strict separation ensures financial audits remain high-performing and free from runtime debug clutter.

### A. Business Database (`paytag_business`)
Holds all transactional data required for financial reporting, store metrics, and inventory compliance.

#### 1. `sessions` Collection
Tracks the lifecycle of individual checkout transactions.
* **Index:** `{ "transaction_number": 1 }` (Unique)
* **Document Schema:**
```json
{
  "transaction_number": "P01112340",
  "status": "FAILED",
  "started_at": "ISODate('2026-10-01T12:00:00Z')",
  "ended_at": "ISODate('2026-10-01T12:01:15Z')",
  "totals": {
    "total_items_scanned": 3,
    "hard_tags_detected": 1,
    "successfully_neutralized": 2,
    "failed_neutralized": 0
  },
  "error_flags": ["NEUTRALIZATION_FAILED"]
}
```

#### 2. `basket_items` Collection
Stores individual security tag tracking details. Enforces unique entries per session and monitors hardware retries.
* **Index:** `{ "transaction_number": 1, "rfid": 1 }` (Unique Compound)
* **Document Schema:**
```json
{
  "transaction_number": "P01112340",
  "barcode": "7290000000001",
  "rfid": "E200001B0000000000000001",
  "is_hard_tag": false,
  "neutralization_status": "SUCCESS",
  "retry_attempts": 0,
  "last_error_code": null,
  "scanned_at": "ISODate('2026-10-01T12:00:05Z')",
  "neutralized_at": "ISODate('2026-10-01T12:01:14Z')"
}
```

### B. Technical Database (`paytag_technical`)
Houses runtime diagnostic information, background heartbeats, and raw hardware faults. Both collections utilize capped storage profiles to protect local terminal disk space.

#### 1. `system_logs` Collection
A unified, chronological technical stream of runtime exceptions and simulator error enums.
* **Configuration:** Capped Collection (Size: 500MB)
* **Index:** `{ "transaction_number": 1, "timestamp": 1 }` (Compound Sort)
* **Design Rule:** Because this collection captures system-wide logs outside of active checkouts, `transaction_number` stores `null` for general events. The compound index leverages native sparse/nullable entry sorting to ensure transactional lookup performance remains instantaneous.
* **Document Schema:**
```json
{
  "transaction_number": "P01112340",
  "timestamp": "ISODate('2026-10-01T12:01:10Z')",
  "hardware_fault": {
    "error_code": 17,
    "error_name": "NotAllTagsNeutralized",
    "user_message": "Some items failed neutralization. Please scan again."
  },
  "code_exception": null,
  "technical_details": {
    "endpoint_called": "/partner/Neutralize",
    "http_status_code": 200,
    "payload_sent": { "Items": [{"Barcode": "7290000000001", "RFID": "E20..."}] },
    "raw_simulator_response": { "FailedRFItems": [...] }
  }
}
```
* **Document Schema (System-Wide Event Example):**
```json
{
  "timestamp": "ISODate('2026-10-01T11:45:00Z')",
  "severity": "INFO",
  "message": "Background key interception hook successfully bound to system inputs.",
  "transaction_number": null,
  "hardware_fault": null,
  "code_exception": null,
  "technical_details": {
    "active_hotkeys": ["s", "n"]
  }
}
```

#### 2. `health_checks` Collection
Tracks periodic background pings of the hardware modules when the terminal is idling.
* **Configuration:** Capped Collection (Size: 50MB)
* **Index:** `{ "timestamp": -1 }`
* **Document Schema:**
```json
{
  "timestamp": "ISODate('2026-10-01T12:05:00Z')",
  "simulator_version": "3.8.34",
  "hardware_status": {
    "reader_connected": true,
    "neutralizer_connected": true,
    "all_connected": true
  },
  "connectivity": {
    "is_simulator_reachable": true,
    "response_time_ms": 12
  }
}
```

## 1.1 In-Memory Cache & Debouncing Strategy
Because the RFID antenna continuously scans and transmits data over consecutive 1000ms polling intervals during the `SCANNING` state, a direct database write approach would flood MongoDB with thousands of redundant write operations for the same items.

To prevent disk I/O bottlenecks, the application implements a lightweight internal memory cache utilizing a native Python `dict` pattern initialized during the `PRE_CHECKOUT` phase.


### Cache Tracking Mechanics
During the checkout lifecycle, the cache stores data elements at the individual tag level rather than capturing full array snapshots. This granular tracking strategy protects data integrity against hardware reading anomalies:

* **Immunity to Sensor Flickering:** RFID antennas face real-world signal distortions where a tag might temporarily drop from a scan block and reappear a second later. By storing unique signatures in a local memory matrix, a tag flickering back online is instantly recognized as an existing item, completely eliminating duplicate database writes.
* **State Reset Compliance:** The local memory array exists strictly within the boundaries of an active transaction. The exact millisecond the state engine transitions to the `FINALIZED` phase, the in-memory dictionary is completely flushed and garbage-collected, ensuring a clean memory footprint for subsequent customers.

### Architectural Justification:
* **Production Trade-offs Considered:** While caching the entire basket array in memory and executing a single bulk database insert at the end of checkout would lower database writes further, it leaves the system vulnerable to total data loss if the terminal crashes mid-transaction. Our implementation of *In-Memory Debouncing + Real-Time Incremental Streaming* achieves the optimal balance: it prevents database spamming while guaranteeing that scanned items are safely persisted to disk immediately upon physical detection.

## 1.2 Database Decoupling & Storage Portability (The Repository Pattern)
To ensure the core business logic remains completely independent of the underlying storage engine, the application adopts the **Repository Pattern**. 

* **The Interface Layer:** The State Machine is entirely banned from accessing database drivers (like `pymongo`) directly. Instead, it interacts exclusively with an abstract data service layer (`db_repository.py`).
* **Portability Benefits:** If the terminal infrastructure transitions away from MongoDB in the future (e.g., migrating to PostgreSQL or an edge SQLite database file), the developer only needs to implement a new repository class. The 7-state core engine remains entirely unchanged, achieving true modular decoupling.

---

## 1.3 Multithreaded Telemetry Architecture & Inter-Thread Message Queue
To isolate system latency and eliminate input lag across system boundaries, the application implements a decoupled, asynchronous concurrency model. Rather than forcing threads to execute blocking actions or manage messy cross-thread states directly, communication is synchronized via a **"Many Providers, One Consumer" Inter-Thread Message Queue** pattern using Python's native, thread-safe `queue.Queue`.

To eliminate performance degradation, the application implements an asynchronous, thread-pooled architecture:

---

## 2. Configuration Strategy (YAML Decoupling)
To prevent environment hardcoding and ensure portability between local simulator environments and physical store deployments, all runtime values decouple into a `config.yaml` layout.

### Configuration Layout (`config.yaml`)
```yaml
environment: "development"

simulator:
  base_url: "http://localhost:8765"
  polling_interval_ms: 1000
  timeout_seconds: 5

database:
  mongo_uri: "mongodb://localhost:27017"
  business_db_name: "paytag_business"
  technical_db_name: "paytag_technical"
  min_log_level: "WARNING"              # Options: DEBUG, INFO, WARNING, ERROR
  capped_collections:
    transaction_errors_max_size: "500MB"  
    health_checks_max_size: "50MB"       

hardware_settings:
  hotkeys:
    start_session: "s"
    neutralize_session: "n"
  
  max_neutralize_retries: 3         # Retries if hardware fails a deactivation pulse
  retry_delay_ms: 500               # Static delay between hardware retries

  max_network_connect_retries: 2    # Fast retries if network call drops or times out
  network_retry_delay_ms: 200       # Packet retry delay envelope
```

### Architectural Justification:
* **Human-Readable Limits:** Capped constraints use descriptive string formatting (`"500MB"`). A parser utility in the initialization layer programmatically converts these into byte integers for native driver execution, eliminating configuration calculations.
* **Dual-Layer Retry Isolation:** The engine isolates **Hardware Retries** from **Network Retries**. If an API request encounters a transient network timeout, it fires rapid connection retries (`200ms` delay) to bypass packet loss. If the call completes successfully but returns a structural hardware error code, it flips to the slower hardware retry strategy (`500ms` delay). This keeps short network drops from forcing a total transaction failure.

---

## 3. The Core Shopping State Engine
To achieve deterministic, fault-tolerant execution, the application is structured as a Finite State Machine (FSM) comprising 7 discrete states. Transitions between states are tightly guarded to eliminate asynchronous race conditions.

### State Catalog & Transition Rules

1. **INITIALIZING (System Startup):** Parses `config.yaml`, binds database handshakes, confirms capped parameters exist, and executes a bootup query to `GET /info`. On complete success, routes to `IDLE`. If critical elements are offline, jumps immediately to `MALFUNCTION`.
2. **IDLE (Waiting for Customer):** Keyboard hooks register *exclusively* to listen for the start hotkey (`S`). A background scheduler checks terminal health via `GET /info` once every 10 minutes when sitting unused. Intercepting `S` fires an instantaneous transition to `PRE_CHECKOUT`.
3. **PRE_CHECKOUT (Transaction Preparation):** Runs completely automatically behind the scenes. Generates a unique string `transaction_number`, commits an `OPEN` database entry inside `paytag_business.sessions`, and prepares the working RAM array grids. Automatically shifts forward into `SCANNING` the microsecond write confirmation succeeds. If a database timeout occurs, logs a trace and drops to `MALFUNCTION`.
4. **SCANNING (Basket Assembly):** Keyboard listener switches to track *exclusively* the completion hotkey (`N`). Launches a background thread polling `POST /partner/GetItems` every 1000ms, streaming real-time basket readouts to the terminal screen and upserting into `basket_items`. Tapping `N` safely kills the loop and moves to `NEUTRALIZING`. 
5. **NEUTRALIZING (Tag Deactivation):** Code inspects items in memory. Entities with `is_hard_tag: True` are stripped entirely from the incoming API array payload and flagged inside local records as `SKIPPED_MANUAL_REMOVAL`, flashing an explicit warning to the cashier to manually detach the clip. Remaining elements are packed and dispatched to `POST /partner/Neutralize`.
6. **FINALIZED (Transaction Wrap-up):** Evaluates success statuses (ErrorCode 0 vs ErrorCode 17), updates corresponding records in `basket_items`, completes the parent session status to `COMPLETED` or `FAILED`, flushes workspace RAM data, draws a receipt block on the console, and loops cleanly back to `IDLE`.
7. **MALFUNCTION (High-Frequency Recovery Lock):** Protective hardware/environment lockout state. The application completely unbinds global keyboard inputs, ignoring all keyboard actions.
   * **Database Isolation Rule:** To safeguard the terminal against cascade logging loops (especially if the database server itself is corrupted or down), **the app is strictly banned from executing database writes inside MALFUNCTION.** It relies entirely on the technical exception trace recorded right before the drop.
   * **Automated Recovery Loop:** Clears the console interface and displays a dedicated maintenance readout indicating whether the lock is an internal code issue or an external physical hardware fault (e.g., RFID reader unplugged). Launches an intensive thread that polls the broken resource (MongoDB socket or the `GET /info` API) **once every 1 second**. The terminal stays input-locked until health statuses return online, returning back to `INITIALIZING` for a clean startup reset.

### 3.1 Advanced Hardware Error Handling & Severity Matrix
The application categorizes all 18 simulator response codes into distinct functional severities. This allows our decoupled logging layer to filter operations programmatically based on the configuration file's `min_log_level`.

| Code | Error Name | Assigned Severity | State Machine Reaction Strategy |
| :--- | :--- | :--- | :--- |
| **0** | `None` | `INFO` | Advance state machine naturally. |
| **1** | `GeneralError` | `ERROR` | Log exception, retry request once. |
| **2** | `HardwareGeneralError` | `CRITICAL` | Halt loop, transition directly to `MALFUNCTION`. |
| **3** | `HardwareRequestTimeout`| `WARNING` | Invoke network retry loop layer. |
| **4** | `ReaderNotConnected` | `CRITICAL` | Force `MALFUNCTION` lockout state. Clear UI screen. |
| **5** | `TagReadError` | `WARNING` | Log soft warning to console; retry next poll cycle. |
| **6** | `ReaderBusy` | `INFO` | Pause terminal printing for 1 tick; retry next loop. |
| **7** | `LowSignalStrength` | `WARNING` | Print "Adjust Basket Items" on console; continue loop. |
| **8** | `NeutralizerNotConnected`| `CRITICAL` | Abort checkout sequence, force `MALFUNCTION` lock. |
| **9** | `HardTagReleaseError` | `ERROR` | Halt sequence, alert cashier to manually detach pin. |
| **10** | `CommunicationError` | `ERROR` | Fire automated connection retry layer. |
| **11** | `InvalidResponse` | `ERROR` | Log malformed JSON to database; retry once. |
| **12** | `CommandTimeout` | `WARNING` | Execute network connection timeout logic. |
| **13** | `DataCorruption` | `ERROR` | Re-read stream packet. Drop to `MALFUNCTION` if repeated. |
| **14** | `CommunicationReset` | `CRITICAL` | Drop to `MALFUNCTION`. Run 1s self-healing loop. |
| **15** | `SecurityViolation` | `CRITICAL` | Hard-halt session, log security alert, drop to `MALFUNCTION`. |
| **16** | `ConfigurationError` | `CRITICAL` | Hold system in `MALFUNCTION` state at application boot. |
| **17** | `NotAllTagsNeutralized` | `ERROR` | Increment item `retry_attempts`. Retry until max count. |

### Defensive Fault-Isolation Rules:
1. **The Warning Envelope (Codes 5, 6, 7):** These do not trigger database operations or alter the core state. They allow the `SCANNING` background thread to remain highly performant despite temporary physical interference in the RFID tub.
2. **The Hard Lockout Gate (Codes 2, 4, 8, 14, 15, 16):** Instantly revokes keyboard capture hooks, flags the root `error_flags` array inside the active `sessions` row, and transfers control to the database-isolated `MALFUNCTION` loop.

---

## 4. Keyboard Interception State Machine & Execution Flow
To ensure the client stays completely lightweight and free from complex desktop window dependencies, the program executes as a native terminal-bound background engine driven by a context-aware keyboard hook.

### The Alternating Gated Listener
Instead of monitoring all key combinations concurrently—which introduces input bounce, multi-thread collisions, or double-scanning bugs—the hardware hook changes its structural behavior depending on the active state of the Core State Engine:

* **When Core State is IDLE:** The background hook registers exclusively to the start value (`S`). It is physically blind to `N`, meaning an operator clicking the completion button prematurely causes no application state interference.
* **When Core State enters SCANNING:** The listener instantly drops the hook for `S` and shifts all focus to the completion key (`N`). The system cannot be spammed with overlapping transaction initiation triggers. This architectural gated mechanism creates hardware-level immunity against state race conditions.

