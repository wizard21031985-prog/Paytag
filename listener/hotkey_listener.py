# listener/hotkey_listener.py
import sys
from queue import Queue
from datetime import datetime
from pynput import keyboard


class GatedHotkeyListener:
    def __init__(self, config: dict, main_queue: Queue, logger):
        self.config = config
        self.main_queue = main_queue  # The master pipe back to our main thread consumer
        self.logger = logger  # Injected unified logger service instance

        # Pull hotkey mappings directly from our decoupled YAML configuration matrix
        self.start_key_char = config['hardware_settings']['hotkeys']['start_session'].lower()
        self.neutralize_key_char = config['hardware_settings']['hotkeys']['neutralize_session'].lower()

        # State machine gating variables
        self.is_session_active = False
        self.listener = None

    def start(self):
        """Launches the non-blocking system-wide OS background keyboard hook."""
        self.listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=None
        )
        self.listener.start()

        # Log routine arming trace through our injected logger service
        if self.logger:
            self.logger.log_system_event(
                severity="INFO",
                message=f"Global keyboard hook armed. (Start Gateway: '{self.start_key_char}' | End Gateway: '{self.neutralize_key_char}')"
            )

    def set_session_state(self, active: bool):
        """
        Public method called by the State Machine to dynamically update the gate configuration.
        Forces the listener to toggle its input filters based on active checkout states.
        """
        self.is_session_active = active
        state_name = "ACTIVE TRANSACTION" if active else "IDLE"

        # Log a clean trace showing the hotkey hook gating focus shifting boundaries
        if self.logger:
            self.logger.log_system_event(
                severity="INFO",
                message=f"Hotkey interceptor focus boundary shifted to context gate: {state_name}"
            )

    def _on_key_press(self, key):
        """Internal callback fired by the OS layer whenever any physical key is stroke down."""
        try:
            # Safely extract alphanumeric character value from the pynput key event object
            if hasattr(key, 'char') and key.char is not None:
                pressed_char = key.char.lower()
            else:
                return  # Ignore special function commands (Shift, Ctrl, Alt, etc.)

            # --- THE GATED CONTEXT-AWARE STATE SWITCH ---

            if not self.is_session_active:
                # GATED GATE 1: System is Idle. We listen ONLY for the configured start key ('s')
                if pressed_char == self.start_key_char:
                    if self.logger:
                        self.logger.log_system_event(
                            severity="INFO",
                            message=f"Valid hotkey intercepted: '{pressed_char}' trigger matching START condition."
                        )
                    self._dispatch_event("START_KEY_PRESSED")
            else:
                # GATED GATE 2: Transaction Active. We listen ONLY for the configured finish key ('n')
                if pressed_char == self.neutralize_key_char:
                    if self.logger:
                        self.logger.log_system_event(
                            severity="INFO",
                            message=f"Valid hotkey intercepted: '{pressed_char}' trigger matching NEUTRALIZE condition."
                        )
                    self._dispatch_event("NEUTRALIZE_KEY_PRESSED")

        except Exception as e:
            # Safe fallback logging trace to keep the background OS keyboard thread alive
            if self.logger:
                self.logger.log_system_event(
                    severity="ERROR",
                    message=f"Internal keyboard hook processing failure exception: {e}"
                )
            else:
                print(f"[HOTKEY HOOK ERROR] Interception failure anomaly: {e}", file=sys.stderr)

    def _dispatch_event(self, event_type: str):
        """Packages the validated keystroke down into a standard message envelope and dispatches to queue."""
        event_payload = {
            "source": "HARDWARE_KEYBOARD_HOOK",
            "timestamp": datetime.utcnow(),
            "event_type": event_type,
            "is_fatal": False
        }

        # Drop the event message onto the central main queue conveyor belt for processing
        self.main_queue.put(event_payload)

    def stop(self):
        """Safely tears down the OS system hook wrapper loop on application close down."""
        if self.listener:
            self.listener.stop()
            if self.logger:
                self.logger.log_system_event(
                    severity="INFO",
                    message="Global keyboard hook safely disarmed and detached from OS input stream."
                )
