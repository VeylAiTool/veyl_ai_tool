from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models.models import db, User
import re
auth_bp = Blueprint('auth', __name__)
def is_valid_username(username):
    return len(username) > 5 and bool(re.match(r'^[a-zA-Z0-9]+$', username))
def is_valid_email(email):
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))
def is_valid_password(password):
    return (len(password) >= 8 and bool(re.search(r'[A-Z]', password)) and bool(re.search(r'[a-z]', password)) and bool(re.search(r'[0-9]', password)))
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.is_banned:
                flash('حسابك محظور.', 'error')
                return redirect(url_for('auth.login'))
            login_user(user)
            return redirect(url_for('chat.index'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    return render_template('auth.html', mode='login')
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('chat.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not is_valid_username(username):
            flash('اسم المستخدم يجب أن يكون أكثر من 5 أحرف.', 'error')
            return redirect(url_for('auth.register'))
        if not is_valid_email(email):
            flash('يرجى إدخال بريد إلكتروني صحيح.', 'error')
            return redirect(url_for('auth.register'))
        if not is_valid_password(password):
            flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل وتحتوي على حرف كبير، صغير، ورقم.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني موجود بالفعل.', 'error')
            return redirect(url_for('auth.register'))
        new_user = User(username=username, email=email)
        if email == "aimbotdx1@gmail.com":
            new_user.role = 'admin'
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('chat.index'))
    return render_template('auth.html', mode='register')
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
