from . import db
from datetime import datetime

def generate_request_number():
    year = datetime.now().year
    count = LeaveRequest.query.count() + 1
    return f"LR-{year}-{count:05d}"

class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"
    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(20), unique=True, nullable=False)

    # Active language when form was submitted: "en" or "ar"
    active_language = db.Column(db.String(5), default="en", nullable=False)

    # English fields
    employee_username = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(100), nullable=False)
    employee_department = db.Column(db.String(100))
    employee_number = db.Column(db.String(20))
    reason = db.Column(db.Text, nullable=False)
    destination = db.Column(db.String(200))
    manager_name = db.Column(db.String(100), nullable=False)

    # Arabic fields
    employee_name_ar = db.Column(db.String(200), default="")
    employee_department_ar = db.Column(db.String(200), default="")
    reason_ar = db.Column(db.Text, default="")
    destination_ar = db.Column(db.String(200), default="")
    manager_name_ar = db.Column(db.String(200), default="")

    # Dates (shared)
    departure_datetime = db.Column(db.DateTime, nullable=False)
    return_datetime = db.Column(db.DateTime, nullable=False)

    # Status
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    printed_at = db.Column(db.DateTime, nullable=True)

    def is_editable(self):
        return self.status in ("draft", "pending")

    def is_arabic(self):
        return self.active_language == "ar"

    def status_badge_class(self):
        return {
            "draft": "badge-draft",
            "pending": "badge-pending",
            "approved": "badge-approved",
            "archived": "badge-archived",
        }.get(self.status, "badge-draft")
