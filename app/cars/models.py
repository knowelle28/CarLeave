from app import db
from datetime import datetime


class Car(db.Model):
    __tablename__ = "cars"
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    plate_number_ar = db.Column(db.String(20), default="")
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(30), default="")
    color_ar = db.Column(db.String(30), default="")
    seats = db.Column(db.Integer, default=5)
    plate_image = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True)
    current_mileage = db.Column(db.Float, default=0)
    last_major_maintenance = db.Column(db.Date, nullable=True)
    last_minor_maintenance = db.Column(db.Date, nullable=True)
    registration_expiry = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("CarBooking", backref="car", lazy=True)

    def display_name(self):
        return f"{self.year} {self.make} {self.model} — {self.plate_number}"

    def image_url(self):
        if self.plate_image:
            return f"/static/uploads/cars/{self.plate_image}"
        return ""

    def last_return_note(self):
        """Return the note from the most recent completed booking."""
        last = CarBooking.query.filter_by(
            car_id=self.id, status="returned"
        ).order_by(CarBooking.actual_return.desc()).first()
        return last.return_note if last and last.return_note else ""

    def last_borrower_name(self):
        last = CarBooking.query.filter_by(
            car_id=self.id, status="returned"
        ).order_by(CarBooking.actual_return.desc()).first()
        return last.employee_name if last else ""

    def registration_status(self):
        """Returns: 'expired', 'expiring_soon' (within 30 days), or 'ok'"""
        if not self.registration_expiry:
            return 'ok'
        from datetime import date
        today = date.today()
        delta = (self.registration_expiry - today).days
        if delta < 0:
            return 'expired'
        elif delta <= 30:
            return 'expiring_soon'
        return 'ok'

    def registration_days_left(self):
        if not self.registration_expiry:
            return None
        from datetime import date
        return (self.registration_expiry - date.today()).days


class CarBooking(db.Model):
    __tablename__ = "car_bookings"
    id = db.Column(db.Integer, primary_key=True)
    booking_number = db.Column(db.String(20), unique=True, nullable=False)
    car_id = db.Column(db.Integer, db.ForeignKey("cars.id"), nullable=False)

    employee_username = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(100), nullable=False)
    employee_name_ar = db.Column(db.String(200), default="")
    employee_department = db.Column(db.String(100), default="")
    employee_department_ar = db.Column(db.String(200), default="")
    employee_number = db.Column(db.String(20), default="")

    destination = db.Column(db.String(200), default="")
    destination_ar = db.Column(db.String(200), default="")
    purpose = db.Column(db.Text, default="")
    purpose_ar = db.Column(db.Text, default="")

    manager_name = db.Column(db.String(100), nullable=False)
    manager_name_ar = db.Column(db.String(200), default="")

    planned_departure = db.Column(db.DateTime, nullable=False)

    actual_departure = db.Column(db.DateTime, nullable=True)
    actual_return = db.Column(db.DateTime, nullable=True)
    odometer_return = db.Column(db.Float, nullable=True)
    return_note = db.Column(db.Text, default="")   # driver's return note

    active_language = db.Column(db.String(5), default="en")
    status = db.Column(db.String(20), default="pending", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def status_badge_class(self):
        return {
            "pending":  "badge-pending",
            "borrowed": "badge-out",
            "returned": "badge-returned",
            "archived": "badge-archived",
        }.get(self.status, "badge-pending")


def generate_booking_number():
    year = datetime.now().year
    count = CarBooking.query.count() + 1
    return f"CB-{year}-{count:05d}"