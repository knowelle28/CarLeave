from app import db
from datetime import datetime


class HelpDeskCategory(db.Model):
    __tablename__ = "helpdesk_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(200), default="")
    department = db.Column(db.String(100), nullable=False)
    department_ar = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship("HelpDeskTicket", backref="category", lazy=True)


class HelpDeskStaff(db.Model):
    __tablename__ = "helpdesk_staff"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    full_name_ar = db.Column(db.String(200), default="")
    department = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class HelpDeskTicket(db.Model):
    __tablename__ = "helpdesk_tickets"
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    title_ar = db.Column(db.String(400), default="")
    description = db.Column(db.Text, default="")
    description_ar = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("helpdesk_categories.id"), nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False)
    priority = db.Column(db.String(20), default="normal", nullable=False)
    created_by_username = db.Column(db.String(50), nullable=False)
    created_by_name = db.Column(db.String(100), nullable=False)
    created_by_name_ar = db.Column(db.String(200), default="")
    assigned_to_username = db.Column(db.String(50), default="")
    active_language = db.Column(db.String(5), default="en")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = db.relationship("TicketMessage", backref="ticket", lazy=True,
                               order_by="TicketMessage.created_at")

    def status_badge_class(self):
        return {
            "open":        "badge-pending",
            "in_progress": "badge-out",
            "resolved":    "badge-approved",
            "closed":      "badge-archived",
        }.get(self.status, "badge-pending")

    def priority_badge_class(self):
        return {
            "low":    "badge-draft",
            "normal": "badge-pending",
            "high":   "badge-warning",
            "urgent": "badge-danger",
        }.get(self.priority, "badge-pending")


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("helpdesk_tickets.id"), nullable=False)
    sender_username = db.Column(db.String(50), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    sender_name_ar = db.Column(db.String(200), default="")
    body = db.Column(db.Text, nullable=False)
    body_ar = db.Column(db.Text, default="")
    is_staff_reply = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    recipient_username = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    title_ar = db.Column(db.String(400), default="")
    body = db.Column(db.Text, default="")
    body_ar = db.Column(db.Text, default="")
    link = db.Column(db.String(500), default="")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def generate_ticket_number():
    year = datetime.now().year
    count = HelpDeskTicket.query.count() + 1
    return f"HD-{year}-{count:05d}"
