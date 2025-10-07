from flask_mail import Mail, Message
from threading import Thread
from flask import current_app

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print("Alert email sent successfully!")
        except Exception as e:
            print(f"Failed to send email: {e}")

def send_alert_email(subject, recipients, text_body):
    app = current_app._get_current_object()
    msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=recipients)
    msg.body = text_body
    
    # Send email in a background thread to avoid blocking the application
    thread = Thread(target=send_async_email, args=[app, msg])
    thread.start()