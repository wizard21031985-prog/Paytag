# app.py
import sys
import time
from config.app_initializer import ApplicationInitializer


class PayTagApplication:
    def __init__(self):
        # Delegate setup to initializer (it will log its own bootstrapping steps)
        initializer = ApplicationInitializer("config.yaml")
        self.context = initializer.bootstrap()

        # Core components remain pristine placeholders until context injection
        self.state_machine = None
        self.hotkey_listener = None

    def run(self):
        """Launches the verified application components using the injected context settings."""
        env = self.context.config['environment']
        sim_url = self.context.config['simulator']['base_url']

        # Log terminal environment configurations on system activation
        self.context.logger.log_system_event(
            severity="INFO",
            message=f"Terminal client active. Cluster envelope mode: '{env}'"
        )
        self.context.logger.log_system_event(
            severity="INFO",
            message=f"Listening for edge hardware simulator targets at: {sim_url}"
        )
        self.context.logger.log_system_event(
            severity="INFO",
            message="Core infrastructure ready. Awaiting state machine loop hooks."
        )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Executes orderly disconnects and handles thread pool worker drainage on application closure."""
        # Log a warning to signify the application process is shutting down
        self.context.logger.log_system_event(
            severity="WARNING",
            message="Process loop execution interrupted by user command. Initiating graceful terminal teardown..."
        )

        # Gracefully shut down the asynchronous logger thread pool worker queue
        if self.context.logger:
            try:
                self.context.logger.shutdown()
                # Final local stdout flush as the thread pool closes down
                sys.stdout.write(
                    f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] [INFO] [TEARDOWN] Asynchronous logging workers safely drained.\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stderr.write(
                    f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] [ERROR] [TEARDOWN WARNING] Error draining logger pools: {e}\n")
                sys.stderr.flush()

        sys.stdout.write(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] [INFO] [TEARDOWN] PayTag Terminal Integration client completely offline.\n")
        sys.stdout.flush()
        sys.exit(0)
