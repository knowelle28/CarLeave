import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    env = os.environ.get("APP_ENV", "development")
    if env == "production":
        app.config.from_object("config.prod")
    else:
        app.config.from_object("config.dev")

    # Make sure upload folder exists
    upload_dir = os.path.join(app.root_path, "static", "uploads", "cars")
    os.makedirs(upload_dir, exist_ok=True)

    db.init_app(app)

    # Register LeavePass blueprint
    from .routes import main
    app.register_blueprint(main)

    # Register Car Booking blueprint
    from .cars import cars_bp
    app.register_blueprint(cars_bp)

    # Register Help Desk blueprint
    from .helpdesk import helpdesk_bp
    app.register_blueprint(helpdesk_bp)

    @app.context_processor
    def inject_helpdesk_globals():
        from flask import session as _session
        user = _session.get("user")
        if not user:
            return {"unread_notifications": 0, "is_helpdesk_staff": False}
        try:
            from app.helpdesk.models import Notification, HelpDeskStaff
            username = user.get("username", "")
            unread = Notification.query.filter_by(
                recipient_username=username, is_read=False
            ).count()
            staff = HelpDeskStaff.query.filter_by(
                username=username, is_active=True
            ).first()
            return {
                "unread_notifications": unread,
                "is_helpdesk_staff": staff is not None,
            }
        except Exception:
            return {"unread_notifications": 0, "is_helpdesk_staff": False}

    with app.app_context():
        db.create_all()
        # Seed 5 placeholder cars if fleet is empty
        from .cars.models import Car
        if Car.query.count() == 0:
            _seed_cars()

    return app


def _seed_cars():
    from .cars.models import Car
    placeholder_cars = [
        Car(plate_number="12345 AB", make="Toyota", model="Land Cruiser",
            year=2022, color="White", color_ar="أبيض", seats=7,
            plate_number_ar="أ ب 12345"),
        Car(plate_number="67890 CD", make="Nissan", model="Patrol",
            year=2021, color="Silver", color_ar="فضي", seats=7,
            plate_number_ar="ج د 67890"),
        Car(plate_number="11223 EF", make="Toyota", model="Camry",
            year=2023, color="Black", color_ar="أسود", seats=5,
            plate_number_ar="هـ و 11223"),
        Car(plate_number="44556 GH", make="Mitsubishi", model="Pajero",
            year=2020, color="Grey", color_ar="رمادي", seats=7,
            plate_number_ar="ج هـ 44556"),
        Car(plate_number="77889 IJ", make="Ford", model="Explorer",
            year=2022, color="Blue", color_ar="أزرق", seats=6,
            plate_number_ar="ي ك 77889"),
    ]
    from . import db
    for car in placeholder_cars:
        db.session.add(car)
    db.session.commit()
