import os
from datetime import datetime
from flask import Flask, render_template, url_for, redirect, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from alembic import op
import sqlalchemy as sa

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

if 'PYTHONANYWHERE_DOMAIN' in os.environ:
    SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="imak02",
    password="44pass44",
    hostname="imak02.mysql.eu.pythonanywhere-services.com",
    databasename="imak02$users",
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.relationship('Note', backref='author', lazy=True)
    groups = db.relationship('Group', backref='owner', lazy=True)
    members = db.relationship('Member', backref='user', lazy=True)

    def __init__(self, name, email, password, is_admin=False):
        self.name = name
        self.email = email
        self.password = password
        self.is_admin = is_admin

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.relationship('Note', backref='group', lazy=True)

class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    notes = db.relationship('Note', backref='member', lazy=True)

    def __repr__(self):
        return f"Member('{self.name}', '{self.email}')"

def upgrade():
    op.add_column('members', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='False'))

def downgrade():
    op.drop_column('members', 'is_admin')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email address already exists')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='sha256')
        is_admin = User.query.count() == 0 # True if first user, False otherwise
        new_user = User(name=name, email=email, password=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful, please log in')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('dashboard')
        return redirect(next_page)

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        note_content = request.form.get('content')
        group_id = request.form.get('group_id')
        member_id = request.form.get('member_id')
        if not member_id:
            member_id = current_user.members[0].id
        new_note = Note(content=note_content, user_id=current_user.id, group_id=group_id, member_id=member_id)
        db.session.add(new_note)
        db.session.commit()
        flash('Note added successfully')
        return redirect(url_for('dashboard'))

    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.date_created.desc()).all()
    groups = Group.query.filter_by(user_id=current_user.id).all()
    members = Member.query.filter_by(user_id=current_user.id).all()
    if not members:
        new_member = Member(name=current_user.name, email=current_user.email, password=current_user.password, user_id=current_user.id, is_admin = 1)
        db.session.add(new_member)
        db.session.commit()
        members = [new_member]

    # Add "(admin)" to the admin's name
    for member in members:
        if member.email == current_user.email:
            member.name += "  (admin)"
            break

    return render_template('dashboard.html', notes=notes, groups=groups, members=members)

@app.route('/groups', methods=['GET', 'POST'])
@login_required
def groups():
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        new_group = Group(name=group_name, user_id=current_user.id)
        db.session.add(new_group)
        db.session.commit()
        flash('Group added successfully')
        return redirect(url_for('groups'))

    groups = Group.query.filter_by(user_id=current_user.id).all()
    return render_template('groups.html', groups=groups)

@app.route('/members', methods=['GET', 'POST'])
@login_required
def members():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='sha256')

        if len(current_user.members) >= 5:
            flash("You can only add up to 5 members.")
            return redirect(url_for('members'))

        new_member = Member(name=name, email=email, password=hashed_password, user_id=current_user.id)
        try:
            db.session.add(new_member)
            db.session.commit()
            flash('Member added successfully.')
        except IntegrityError:
            db.session.rollback()
            flash('This email address is already being used. Please use a different email address.', 'error')
        return redirect(url_for('members'))

    members = current_user.members
    return render_template('members.html', members=members)

@app.route('/add_member', methods=['POST'])
@login_required
def add_member():
    if len(current_user.members) >= 5:
        flash('You can only add up to 5 members.')
        return redirect(url_for('dashboard'))

    member_name = request.form.get('member_name') # Add this line to get the member's name from the form
    if not member_name:
        flash('Please enter a name for the new member.')
        return redirect(url_for('dashboard'))
    member_email = request.form.get('member_email')
    member_password = request.form.get('password')
    
    existing_member = Member.query.filter_by(email=member_email).first()
    if existing_member:
        flash('This email is already registered as a member.')
        return redirect(url_for('dashboard'))

    new_member = Member(name=member_name, email=member_email, password=member_password, user_id=current_user.id) # Add the member's name to the constructor
    db.session.add(new_member)
    db.session.commit()
    flash('Member added successfully.')
    return redirect(url_for('dashboard'))

@app.route('/delete-member/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    if current_user.is_admin:
        member = Member.query.get(member_id)
        if member.is_admin:
            flash('You cannot delete admin')
        else:
            db.session.delete(member)
            db.session.commit()
            flash('Member deleted successfully')
    else:
        flash('You are not authorized to delete users!')
    return redirect(url_for('members'))

@app.route('/delete_note/<int:note_id>')
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        abort(403)

    db.session.delete(note)
    db.session.commit()
    flash('Note deleted successfully')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)

