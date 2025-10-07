from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import random
import socket
import struct
from sqlalchemy import func
import requests

# Local imports
from extensions import db
from models.attack_log import AttackLog
from utils.email_alerts import mail, send_alert_email

# --- App Configuration ---
app = Flask(__name__)
app.config.from_object('config.Config')
db.init_app(app)
mail.init_app(app)
socketio = SocketIO(app)

# --- Global Data ---
geolocation_cache = {}
alert_settings = {
    'is_enabled': False, 'recipient_email': '', 'threshold_count': 20,
    'threshold_minutes': 5, 'last_alert_time': None
}

# --- Background Task Functions ---
def check_for_alerts():
    # This function remains unchanged
    with app.app_context():
        if not all([alert_settings['is_enabled'], alert_settings['recipient_email']]): return
        cooldown = timedelta(minutes=15)
        if alert_settings['last_alert_time'] and (datetime.now() - alert_settings['last_alert_time'] < cooldown): return
        time_thresh = datetime.now() - timedelta(minutes=alert_settings['threshold_minutes'])
        count = AttackLog.query.filter(AttackLog.timestamp >= time_thresh).count()
        if count >= alert_settings['threshold_count']:
            subject = "Honeypot Security Alert: High Attack Volume"
            body = f"Alert: {count} attacks detected, exceeding threshold of {alert_settings['threshold_count']}."
            send_alert_email(subject, [alert_settings['recipient_email']], body)
            alert_settings['last_alert_time'] = datetime.now()

def simulate_attack():
    with app.app_context():
        ip = generate_random_ip()
        # "Brute Force" has been REMOVED from this list
        attack_type = random.choice(['SQL Injection', 'XSS', 'DDoS', 'Phishing'])
        new_log = AttackLog(timestamp=datetime.now(), ip_address=ip, attack_type=attack_type, details=f"Simulated {attack_type} attack.")
        db.session.add(new_log)
        db.session.commit()
        socketio.emit('new_attack', {
            'timestamp': new_log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': new_log.ip_address,
            'attack_type': new_log.attack_type
        })

def background_task_runner(task_function, interval_seconds):
    while True:
        socketio.sleep(interval_seconds)
        task_function()

# --- Main App Routes ---
@app.route('/')
def home():
    initial_activity = AttackLog.query.order_by(AttackLog.timestamp.desc()).limit(10).all()
    return render_template('index.html', recent_activity=initial_activity)

# Login page functionality is now completely disabled.
@app.route('/login')
def login():
    return "<h1>Login Honeypot is disabled.</h1>", 404

@app.route('/log-failed-login', methods=['POST'])
def log_failed_login():
    return jsonify({'status': 'ignored'}), 200

@app.route('/logs')
def logs():
    all_logs = AttackLog.query.order_by(AttackLog.timestamp.desc()).all()
    return render_template('logs.html', attack_logs=all_logs)

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

# (All your other routes and API endpoints remain the same)
@app.route('/get-alert-settings')
def get_alert_settings():
    settings_copy = alert_settings.copy()
    if settings_copy['last_alert_time']: settings_copy['last_alert_time'] = settings_copy['last_alert_time'].isoformat()
    return jsonify(settings_copy)

@app.route('/save-alert-settings', methods=['POST'])
def save_alert_settings():
    data = request.get_json()
    alert_settings['is_enabled'] = data.get('is_enabled', False)
    alert_settings['recipient_email'] = data.get('recipient_email', '')
    alert_settings['threshold_count'] = int(data.get('threshold_count', 20))
    alert_settings['threshold_minutes'] = int(data.get('threshold_minutes', 5))
    return jsonify({'status': 'success'})

@app.route('/test-email')
def test_email():
    try:
        subject = "Honeypot Test Email"
        recipients = ["prajwalhpatil22@gmail.com"] # Replace with your test email
        body = "This is a test email from your Honeypot application."
        send_alert_email(subject, recipients, body)
        return "Attempted to send test email. Check your terminal for success or error messages."
    except Exception as e:
        return f"An error occurred: {e}"

@app.route('/api/attack_frequency')
def api_attack_frequency():
    labels = ["SQL Injection", "XSS", "Brute Force", "DDoS", "Phishing"]
    attack_counts = {label: 0 for label in labels}
    attack_type_counts = db.session.query(AttackLog.attack_type, func.count(AttackLog.attack_type)).group_by(AttackLog.attack_type).all()
    for attack_type, count in attack_type_counts:
        if attack_type in attack_counts: attack_counts[attack_type] = count
    data = [attack_counts[label] for label in labels]
    return jsonify({"labels": labels, "datasets": [{"data": data, "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"]}]})

@app.route('/api/attack_trend')
def api_attack_trend():
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    attacks_per_month = {i: 0 for i in range(1, 13)}
    current_year = datetime.now().year
    monthly_counts = db.session.query(func.extract('month', AttackLog.timestamp), func.count(AttackLog.id)).filter(func.extract('year', AttackLog.timestamp) == current_year).group_by(func.extract('month', AttackLog.timestamp)).all()
    for month, count in monthly_counts: attacks_per_month[int(month)] = count
    data = [attacks_per_month[i] for i in range(1, 13)]
    return jsonify({"labels": months, "datasets": [{"label": "Attacks Over Time", "data": data, "borderColor": "#00ff95", "backgroundColor": "rgba(0, 255, 149, 0.2)"}]})
    
@app.route('/api/attack_locations')
def api_attack_locations():
    attack_locations = []
    recent_attacks = AttackLog.query.order_by(AttackLog.timestamp.desc()).limit(100).all()
    unique_ips = list(set([log.ip_address for log in recent_attacks]))
    ips_to_fetch = [ip for ip in unique_ips if ip not in geolocation_cache]
    if ips_to_fetch:
        try:
            response = requests.post("http://ip-api.com/batch", json=ips_to_fetch, params={'fields': 'query,lat,lon,status'}, timeout=10)
            response.raise_for_status()
            for data in response.json():
                if data.get('status') == 'success':
                    geolocation_cache[data.get('query')] = {'lat': data.get('lat'), 'lon': data.get('lon')}
        except requests.exceptions.RequestException as e:
            print(f"Geolocation API failed: {e}")
    for attack in recent_attacks:
        geo_info = geolocation_cache.get(attack.ip_address)
        if geo_info:
            attack_locations.append({'lat': geo_info['lat'], 'lon': geo_info['lon'], 'type': attack.attack_type})
    return jsonify(attack_locations)

def generate_random_ip():
    if random.random() < 0.2: return "103.27.70.100"
    while True:
        ip = socket.inet_ntoa(struct.pack('>I', random.randint(1, 0xffffffff)))
        parts = [int(p) for p in ip.split('.')]
        if any([parts[0] == 10, (parts[0] == 172 and 16 <= parts[1] <= 31), (parts[0] == 192 and parts[1] == 168), parts[0] == 127, (parts[0] == 169 and parts[1] == 254), parts[0] >= 224]):
            continue
        return ip

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    socketio.start_background_task(target=background_task_runner, task_function=simulate_attack, interval_seconds=5)
    socketio.start_background_task(target=background_task_runner, task_function=check_for_alerts, interval_seconds=60)
    
    socketio.run(app, debug=True)