import os
from datetime import date
from functools import wraps
import mysql.connector
from flask import Flask, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash

# ---- MySQL connection (your existing database) ----
DB = dict(host="localhost", user="root", password="Soorya@0213", database="blood_donor_db")
GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

# ---- Admin login ----
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret')


def q(sql, args=(), one=False, write=False):
    """Run one SQL statement and return rows (or the new row id for writes)."""
    db = mysql.connector.connect(**DB)
    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute(sql, args)
        if write:
            db.commit()
            return cursor.lastrowid
        return cursor.fetchone() if one else cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def ensure_admin():
    """Create the admin account if missing, and make sure it is marked as admin."""
    if q("SELECT id FROM users WHERE email=%s", (ADMIN_EMAIL,), one=True):
        q("UPDATE users SET is_admin=1 WHERE email=%s", (ADMIN_EMAIL,), write=True)
    else:
        q("INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s,%s,%s,1)",
          ("admin", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)), write=True)


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('Only the admin can do that.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return wrapper


def donors_list():
    """Only accepted donors can be scheduled, recorded or followed up."""
    return q("SELECT id, name, blood_group FROM donors WHERE status='Accepted' ORDER BY name")


@app.context_processor
def inject():
    return dict(groups=GROUPS, today=date.today().isoformat())


# ---------- Login / register ----------
@app.route('/')
def home():
    return redirect(url_for('dashboard'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        f = request.form
        if f['password'] != f['confirm_password'] or len(f['password']) < 6:
            flash('Passwords must match and be at least 6 characters.', 'danger')
        elif q("SELECT id FROM users WHERE email=%s OR username=%s", (f['email'], f['username']), one=True):
            flash('A user with this email or username already exists.', 'danger')
        else:
            q("INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s)",
              (f['username'], f['email'], generate_password_hash(f['password'])), write=True)
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = q("SELECT * FROM users WHERE email=%s", (request.form['email'],), one=True)
        if u and check_password_hash(u['password_hash'], request.form['password']):
            session['user_id'], session['username'] = u['id'], u['username']
            session['is_admin'] = bool(u['is_admin'])
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------- Dashboard ----------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
        donors=q("SELECT COUNT(*) n FROM donors", one=True)['n'],
        donations=q("SELECT COUNT(*) n FROM donation_records", one=True)['n'],
        stock=q("SELECT COALESCE(SUM(units_available),0) n FROM blood_stock", one=True)['n'],
        upcoming=q("""SELECT s.scheduled_date, d.name, d.blood_group FROM donation_schedule s
                      JOIN donors d ON d.id=s.donor_id WHERE s.scheduled_date>=CURDATE()
                      ORDER BY s.scheduled_date LIMIT 5"""))


# ---------- Donors ----------
@app.route('/register_donor', methods=['GET', 'POST'])
@login_required
def register_donor():
    if request.method == 'POST':
        f = request.form
        if q("SELECT id FROM donors WHERE email=%s", (f['email'],), one=True):
            flash('A donor with this email already exists.', 'danger')
        else:
            q("""INSERT INTO donors (name,email,phone,blood_group,age,gender,last_donation_date,status)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending')""",
              (f['name'], f['email'], f['phone'], f['blood_group'], f['age'], f['gender'],
               f['last_donation_date'] or None), write=True)
            flash('Donor registered. Waiting for admin approval.', 'success')
            return redirect(url_for('donor_search'))
    return render_template('register_donor.html')


@app.route('/donor_search')
@login_required
def donor_search():
    bg = request.args.get('blood_group', '')
    sql, args = "SELECT * FROM donors", ()
    if bg:
        sql, args = sql + " WHERE blood_group=%s", (bg,)
    return render_template('donor_search.html', donors=q(sql + " ORDER BY name", args), bg=bg)


# ---------- Admin only: approvals queue ----------
@app.route('/admin_donors')
@admin_required
def admin_donors():
    status = request.args.get('status', 'Pending')
    if status not in ('Pending', 'Accepted', 'Rejected'):
        status = 'Pending'
    rows = q("SELECT * FROM donors WHERE status=%s ORDER BY name", (status,))
    counts = {r['status']: r['n'] for r in q("SELECT status, COUNT(*) n FROM donors GROUP BY status")}
    return render_template('admin_donors.html', donors=rows, status=status, counts=counts)


@app.route('/donor_status/<int:donor_id>', methods=['POST'])
@admin_required
def donor_status(donor_id):
    action = request.form.get('action')
    current = request.form.get('current', 'Pending')
    if action == 'accept':
        q("UPDATE donors SET status='Accepted' WHERE id=%s", (donor_id,), write=True)
        q("DELETE FROM rejected_donors WHERE donor_id=%s", (donor_id,), write=True)
        flash('Donor accepted.', 'success')
    elif action == 'reject':
        reason = request.form.get('reason', '').strip() or 'Rejected by admin'
        q("UPDATE donors SET status='Rejected' WHERE id=%s", (donor_id,), write=True)
        q("DELETE FROM rejected_donors WHERE donor_id=%s", (donor_id,), write=True)
        q("INSERT INTO rejected_donors (donor_id, rejection_reason, rejection_date) VALUES (%s,%s,%s)",
          (donor_id, reason, date.today()), write=True)
        flash('Donor rejected.', 'success')
    return redirect(url_for('admin_donors', status=current))


@app.route('/delete_donor/<int:donor_id>', methods=['POST'])
@admin_required
def delete_donor(donor_id):
    # Remove the donor's related rows first, then the donor
    for table in ['post_donation_followup', 'donation_schedule',
                  'rejected_donors', 'donation_records']:
        q(f"DELETE FROM {table} WHERE donor_id=%s", (donor_id,), write=True)
    q("DELETE FROM donors WHERE id=%s", (donor_id,), write=True)
    flash('Donor deleted.', 'success')
    return redirect(url_for('admin_donors', status=request.form.get('current', 'Pending')))


# ---------- Schedule, records, stock ----------
@app.route('/schedule_donation', methods=['GET', 'POST'])
@login_required
def schedule_donation():
    if request.method == 'POST':
        q("INSERT INTO donation_schedule (donor_id, scheduled_date) VALUES (%s,%s)",
          (request.form['donor_id'], request.form['scheduled_date']), write=True)
        flash('Donation scheduled.', 'success')
        return redirect(url_for('schedule_donation'))
    rows = q("""SELECT s.*, d.name, d.blood_group FROM donation_schedule s
                JOIN donors d ON d.id=s.donor_id ORDER BY s.scheduled_date DESC""")
    return render_template('schedule_donation.html', donors=donors_list(), rows=rows)


@app.route('/donation_records', methods=['GET', 'POST'])
@login_required
def donation_records():
    if request.method == 'POST':
        f = request.form
        q("""INSERT INTO donation_records (donor_id,donation_date,volume_ml,hemoglobin_level,status)
             VALUES (%s,%s,%s,%s,'Completed')""",
          (f['donor_id'], f['donation_date'], f['volume_ml'], f['hemoglobin_level'] or None), write=True)
        q("UPDATE donors SET last_donation_date=%s WHERE id=%s", (f['donation_date'], f['donor_id']), write=True)
        q("""UPDATE blood_stock SET units_available=units_available+1
             WHERE blood_group=(SELECT blood_group FROM donors WHERE id=%s)""", (f['donor_id'],), write=True)
        flash('Donation record added.', 'success')
        return redirect(url_for('donation_records'))
    rows = q("""SELECT r.*, d.name, d.blood_group FROM donation_records r
                JOIN donors d ON d.id=r.donor_id ORDER BY r.donation_date DESC""")
    return render_template('donation_records.html', donors=donors_list(), rows=rows)


@app.route('/blood_stock')
@login_required
def blood_stock():
    return render_template('blood_stock.html', rows=q("SELECT * FROM blood_stock ORDER BY blood_group"))


# ---------- Reports (admin only) and rejected list ----------
@app.route('/reports')
@admin_required
def reports():
    return render_template('reports.html', rows=q("""SELECT d.blood_group, COUNT(r.id) total
        FROM donors d JOIN donation_records r ON r.donor_id=d.id GROUP BY d.blood_group ORDER BY total DESC"""))


@app.route('/rejected_donors')
@login_required
def rejected_donors():
    return render_template('rejected_donors.html', rows=q("""
        SELECT d.name, d.blood_group,
               COALESCE(x.rejection_reason, 'Rejected by admin') AS rejection_reason,
               x.rejection_date
        FROM donors d
        LEFT JOIN rejected_donors x ON x.donor_id = d.id
        WHERE d.status = 'Rejected'
        ORDER BY x.rejection_date DESC"""))


# ---------- Compatibility ----------
COMPAT = {'O-': GROUPS, 'O+': ['O+', 'A+', 'B+', 'AB+'], 'A-': ['A-', 'A+', 'AB-', 'AB+'],
          'A+': ['A+', 'AB+'], 'B-': ['B-', 'B+', 'AB-', 'AB+'], 'B+': ['B+', 'AB+'],
          'AB-': ['AB-', 'AB+'], 'AB+': ['AB+']}


@app.route('/compatibility', methods=['GET', 'POST'])
@login_required
def compatibility():
    d = r = ok = None
    if request.method == 'POST':
        d, r = request.form['donor_bg'], request.form['recipient_bg']
        ok = r in COMPAT.get(d, [])
    return render_template('compatibility.html', ok=ok, d=d, r=r)


# ---------- Follow-ups ----------
@app.route('/post_donation_followup', methods=['GET', 'POST'])
@login_required
def post_donation_followup():
    if request.method == 'POST':
        f = request.form
        q("INSERT INTO post_donation_followup (donor_id, followup_date, notes) VALUES (%s,%s,%s)",
          (f['donor_id'], f['followup_date'], f['notes']), write=True)
        flash('Follow-up added.', 'success')
        return redirect(url_for('post_donation_followup'))
    rows = q("""SELECT p.*, d.name FROM post_donation_followup p
                JOIN donors d ON d.id=p.donor_id ORDER BY p.followup_date DESC""")
    return render_template('post_donation_followup.html', donors=donors_list(), rows=rows)


if __name__ == '__main__':
    ensure_admin()
    app.run(debug=True)