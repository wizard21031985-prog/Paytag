# main.py
from app import PayTagApplication

if __name__ == "__main__":
    # Bootstraps the decoupled system application lifecycle manager
    app = PayTagApplication()
    app.run()
