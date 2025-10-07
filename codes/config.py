# config.py

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///honeypot.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# config.py

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///honeypot.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Email Alert Settings ---
    # NOTE: Use an "App Password" from your email provider, not your regular password.
    MAIL_SERVER = 'smtp.gmail.com'  # Example for Gmail
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'lillyflo7502@gmail.com'  # <-- CHANGE THIS
    MAIL_PASSWORD = 'Priyanka9380@' # <-- CHANGE THIS