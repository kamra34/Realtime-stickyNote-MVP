# Create the database by running the following Python code in your project directory:
from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()
