import os
APP_ENV = "development"
AUTH_MODE = "mock"
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://leaveuser:leavepass@db:5432/leaveapp")
SQLALCHEMY_TRACK_MODIFICATIONS = False
MOCK_USERS_FILE = "mock_data/users.json"
SESSION_TYPE = "filesystem"
