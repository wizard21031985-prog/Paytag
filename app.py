# app.py
import sys
import time
from config.app_initializer import ApplicationInitializer


class PayTagApplication:
    def __init__(self):
        # Delegate the entire setup responsibility to the application initializer module
        initializer = ApplicationInitializer("config.yaml")
        self.context = initializer.bootstrap()

        # Core components remain pristine placeholders until context injection
        self.state_machine = None
        self.hotkey_listener = None

    def run(self):
        """Launches the verified application components using the injected context settings."""
        env = self.context.config['environment']
        sim_url = self.context.config['simulator']['base_url']

        print(f"[SYSTEM ACTIVE] Running in '{env}' cluster envelope mode.")
        print(f"[SYSTEM ACTIVE] Listening for edge hardware targets at: {sim_url}")

        try:
            print("\n[READY] Core infrastructure ready. Awaiting state machine loop hooks...")
            print("-> Press Ctrl+C to exit process framework.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Executes orderly disconnects on active application closures."""
        print("\n[SHUTDOWN] Executing graceful terminal resource drainage sequences...")

        # Gracefully shut down the asynchronous logger if it was initialized
        if self.context.logger:
            try:
                self.context.logger.shutdown()
                print("[SHUTDOWN] Asynchronous logging workers safely drained.")
            except Exception as e:
                print(f"[SHUTDOWN WARNING] Error draining logger pools: {e}", file=sys.stderr)

        print("[OFFLINE] PayTag Client completely disconnected.")
        sys.exit(0)
