import os
from datetime import timedelta

APP_ENV = "production"
AUTH_MODE = os.environ.get("AUTH_MODE", "ldap")
SECRET_KEY = os.environ.get("SECRET_KEY")
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SESSION_TYPE = "filesystem"
MOCK_USERS_FILE = "mock_data/users.json"
PERMANENT_SESSION_LIFETIME = timedelta(minutes=10)
