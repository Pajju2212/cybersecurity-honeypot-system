from app import app, db
from models.attack_log import AttackLog

def clear_logs():
    with app.app_context():
        # This command finds all logs where the type is 'Brute Force' and deletes them.
        num_deleted = db.session.query(AttackLog).filter_by(attack_type='Brute Force').delete()
        db.session.commit()
        print(f"Successfully deleted {num_deleted} 'Brute Force' log entries.")

if __name__ == '__main__':
    clear_logs()