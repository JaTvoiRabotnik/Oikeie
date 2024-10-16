import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app

app = create_app()
db = SQLAlchemy(app)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(255))
    token_expiry = db.Column(db.DateTime)
    handle = db.Column(db.String(50), unique=True)

def create_member_table():
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table('member'):
            Member.__table__.create(db.engine)
            print("Created 'member' table.")
        else:
            print("'member' table already exists.")

def add_missing_columns():
    with app.app_context():
        inspector = inspect(db.engine)
        existing_columns = [c['name'] for c in inspector.get_columns('member')]
        for column in Member.__table__.columns:
            if column.name not in existing_columns:
                column_type = column.type.compile(db.engine.dialect)
                nullable = "NULL" if column.nullable else "NOT NULL"
                unique = "UNIQUE" if column.unique else ""
                default = f"DEFAULT {column.default.arg}" if column.default else ""
                with db.engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE member ADD COLUMN {column.name} {column_type} {nullable} {unique} {default}"))
                    conn.commit()
                print(f"Added '{column.name}' column to 'member' table.")

if __name__ == '__main__':
    with app.app_context():
        create_member_table()
        add_missing_columns()
        print("Database migration completed successfully.")
