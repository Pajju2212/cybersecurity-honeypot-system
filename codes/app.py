from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import random
import socket
import struct
from sqlalchemy import func
import requests
from collections import Counter

# Local imports
from extensions import db
from models.attack_log import AttackLog
from utils.email_alerts import mail

# --- App Configuration ---
app = Flask(__name__)
app.config.from_object('config.Config')
db.init_app(app)
mail.init_app(app)
socketio = SocketIO(app, async_mode='threading')

# --- Global Data ---
geolocation_cache = {}
common_usernames = ['admin', 'root', 'user', 'test', 'guest']
common_passwords = ['password', '123456', 'admin', 'qwerty', '12345']

# --- Background Task ---
def simulate_attack():
    with app.app_context():
        ip = generate_random_ip()
        attack_type = random.choice(['SQL Injection', 'XSS', 'DDoS', 'Phishing', 'Brute Force'])
        details = f"Simulated {attack_type} attack."
        if attack_type == 'Brute Force':
            username = random.choice(common_usernames)
            password = random.choice(common_passwords)
            details = f"Failed login attempt with username: '{username}' and password: '{password}'"
        
        new_log = AttackLog(timestamp=datetime.now(), ip_address=ip, attack_type=attack_type, details=details)
        db.session.add(new_log)
        db.session.commit()
        
        socketio.emit('new_attack', {
            'timestamp': new_log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': new_log.ip_address,
            'attack_type': new_log.attack_type
        })
        print(f"Attack Logged: {attack_type} from {ip}")

def background_task_runner(task_function, interval_seconds):
    while True:
        socketio.sleep(interval_seconds)
        task_function()

# --- Main Routes ---
@app.route('/')
def home():
    initial_activity = AttackLog.query.order_by(AttackLog.timestamp.desc()).limit(10).all()
    return render_template('index.html', recent_activity=initial_activity)

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

# --- API Routes ---
@app.route('/api/attack_frequency')
def api_attack_frequency():
    labels = ["SQL Injection", "XSS", "Brute Force", "DDoS", "Phishing"]
    attack_counts = {label: 0 for label in labels}
    try:
        attack_type_counts = db.session.query(AttackLog.attack_type, func.count(AttackLog.attack_type)).group_by(AttackLog.attack_type).all()
        for attack_type, count in attack_type_counts:
            if attack_type in attack_counts:
                attack_counts[attack_type] = count
    except Exception as e:
        print(f"Error fetching attack frequency: {e}")
    data = [attack_counts[label] for label in labels]
    return jsonify({"labels": labels, "datasets": [{"data": data}]})

def _fetch_geo_data(ips_to_fetch):
    if not ips_to_fetch:
        return
    try:
        response = requests.post("http://ip-api.com/batch", json=ips_to_fetch, params={'fields': 'query,country,status'}, timeout=10)
        response.raise_for_status()
        for data in response.json():
            if data.get('status') == 'success':
                geolocation_cache[data.get('query')] = {'country': data.get('country')}
    except requests.exceptions.RequestException as e:
        print(f"Geolocation API failed: {e}")

@app.route('/api/attacks_by_country')
def api_attacks_by_country():
    country_counts = Counter()
    try:
        all_attacks = AttackLog.query.all()
        unique_ips = list(set([log.ip_address for log in all_attacks]))
        
        ips_to_fetch = [ip for ip in unique_ips if ip not in geolocation_cache]
        if ips_to_fetch:
            _fetch_geo_data(ips_to_fetch)

        for attack in all_attacks:
            geo_info = geolocation_cache.get(attack.ip_address)
            if geo_info and geo_info.get('country'):
                country_counts[geo_info['country']] += 1
    except Exception as e:
        print(f"Error fetching country data: {e}")

    top_countries = country_counts.most_common(7)
    labels = [country for country, count in top_countries]
    data = [count for country, count in top_countries]
    
    if len(country_counts) > 7:
        other_count = sum(country_counts.values()) - sum(data)
        if other_count > 0:
            labels.append('Other')
            data.append(other_count)

    return jsonify({"labels": labels, "datasets": [{"data": data}]})

# --- Helper Function & Startup ---
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
    socketio.run(app, debug=True)