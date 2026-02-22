from functools import wraps
from flask import (
    render_template, redirect, url_for, request,
    session, flash, abort
)
from app import db
from app.helpdesk import helpdesk_bp
from app.helpdesk.models import (
    HelpDeskCategory, HelpDeskStaff, HelpDeskTicket,
    TicketMessage, Notification, generate_ticket_number
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _ar():
    return request.form.get("ui_lang", session.get("lang", "en")) == "ar"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user", {}).get("is_admin"):
            flash("Access denied.", "error")
            return redirect(url_for("helpdesk.dashboard"))
        return f(*args, **kwargs)
    return decorated


def helpdesk_staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user", {})
        staff = HelpDeskStaff.query.filter_by(
            username=user.get("username", ""), is_active=True
        ).first()
        if not staff and not user.get("is_admin"):
            flash("Staff access required.", "error")
            return redirect(url_for("helpdesk.dashboard"))
        return f(*args, **kwargs)
    return decorated


def notify(recipient, title, title_ar, body, body_ar, link):
    """Create a notification row. Caller is responsible for committing."""
    n = Notification(
        recipient_username=recipient,
        title=title,
        title_ar=title_ar,
        body=body,
        body_ar=body_ar,
        link=link,
    )
    db.session.add(n)


# ─── User Routes ─────────────────────────────────────────────────────────────

@helpdesk_bp.route("/helpdesk")
@login_required
def dashboard():
    user = session["user"]
    status_filter = request.args.get("status", "all")
    query = HelpDeskTicket.query.filter_by(
        created_by_username=user["username"]
    ).order_by(HelpDeskTicket.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    tickets = query.all()
    return render_template(
        "helpdesk/dashboard.html",
        tickets=tickets,
        status_filter=status_filter,
    )


@helpdesk_bp.route("/helpdesk/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    user = session["user"]
    categories = HelpDeskCategory.query.filter_by(is_active=True).order_by(
        HelpDeskCategory.name
    ).all()

    if request.method == "POST":
        cat_id = request.form.get("category_id", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not cat_id or not title:
            flash(
                "يرجى تحديد الفئة والعنوان." if _ar() else "Please provide category and title.",
                "error",
            )
            return render_template("helpdesk/ticket_form.html",
                                   user=user, categories=categories)

        lang = request.form.get("active_language", "en")
        ticket = HelpDeskTicket(
            ticket_number=generate_ticket_number(),
            title=title,
            title_ar=request.form.get("title_ar", "").strip(),
            description=description,
            description_ar=request.form.get("description_ar", "").strip(),
            category_id=int(cat_id),
            priority=request.form.get("priority", "normal"),
            created_by_username=user["username"],
            created_by_name=user["full_name"],
            created_by_name_ar=user.get("full_name_ar", ""),
            active_language=lang,
            status="open",
        )
        db.session.add(ticket)
        db.session.flush()  # get ticket.id for URL

        # Notify all active staff in that department
        category = HelpDeskCategory.query.get(int(cat_id))
        dept_staff = HelpDeskStaff.query.filter_by(
            department=category.department, is_active=True
        ).all()
        link = url_for("helpdesk.ticket_detail", id=ticket.id, _external=False)
        for s in dept_staff:
            notify(
                recipient=s.username,
                title=f"New Ticket: {ticket.ticket_number}",
                title_ar=f"تذكرة جديدة: {ticket.ticket_number}",
                body=title,
                body_ar=ticket.title_ar or title,
                link=link,
            )

        db.session.commit()
        flash(
            f"تم تقديم التذكرة {ticket.ticket_number} بنجاح." if _ar()
            else f"Ticket {ticket.ticket_number} submitted successfully.",
            "success",
        )
        return redirect(url_for("helpdesk.dashboard"))

    return render_template("helpdesk/ticket_form.html",
                           user=user, categories=categories)


@helpdesk_bp.route("/helpdesk/ticket/<int:id>")
@login_required
def ticket_detail(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    user = session["user"]
    username = user["username"]

    is_owner = ticket.created_by_username == username
    staff = HelpDeskStaff.query.filter_by(username=username, is_active=True).first()
    is_staff_in_dept = bool(staff and ticket.category and
                            staff.department == ticket.category.department)
    is_admin = bool(user.get("is_admin"))

    if not (is_owner or is_staff_in_dept or is_admin):
        abort(403)

    dept_staff = []
    if is_staff_in_dept or is_admin:
        dept = ticket.category.department if ticket.category else ""
        dept_staff = HelpDeskStaff.query.filter_by(
            department=dept, is_active=True
        ).all()

    return render_template(
        "helpdesk/ticket_detail.html",
        ticket=ticket,
        is_owner=is_owner,
        is_staff=is_staff_in_dept or is_admin,
        is_admin=is_admin,
        current_staff=staff,
        dept_staff=dept_staff,
    )


@helpdesk_bp.route("/helpdesk/ticket/<int:id>/reply", methods=["POST"])
@login_required
def user_reply(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    user = session["user"]

    if ticket.created_by_username != user["username"]:
        abort(403)

    body = request.form.get("body", "").strip()
    if not body:
        flash("Reply cannot be empty.", "error")
        return redirect(url_for("helpdesk.ticket_detail", id=id))

    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_username=user["username"],
        sender_name=user["full_name"],
        sender_name_ar=user.get("full_name_ar", ""),
        body=body,
        is_staff_reply=False,
    )
    db.session.add(msg)

    # Notify assigned staff, or all dept staff if unassigned
    link = url_for("helpdesk.ticket_detail", id=ticket.id, _external=False)
    if ticket.assigned_to_username:
        notify(
            recipient=ticket.assigned_to_username,
            title=f"New reply on {ticket.ticket_number}",
            title_ar=f"رد جديد على {ticket.ticket_number}",
            body=body[:120],
            body_ar=body[:120],
            link=link,
        )
    else:
        dept = ticket.category.department if ticket.category else ""
        for s in HelpDeskStaff.query.filter_by(department=dept, is_active=True).all():
            notify(
                recipient=s.username,
                title=f"New reply on {ticket.ticket_number}",
                title_ar=f"رد جديد على {ticket.ticket_number}",
                body=body[:120],
                body_ar=body[:120],
                link=link,
            )

    db.session.commit()
    flash("Reply sent." if not _ar() else "تم إرسال الرد.", "success")
    return redirect(url_for("helpdesk.ticket_detail", id=id))


# ─── Staff Routes ─────────────────────────────────────────────────────────────

@helpdesk_bp.route("/helpdesk/staff")
@login_required
@helpdesk_staff_required
def staff_dashboard():
    user = session["user"]
    staff = HelpDeskStaff.query.filter_by(
        username=user["username"], is_active=True
    ).first()

    status_filter = request.args.get("status", "all")
    priority_filter = request.args.get("priority", "all")

    if staff:
        dept = staff.department
        # Get category IDs for this department
        cat_ids = [c.id for c in HelpDeskCategory.query.filter_by(department=dept).all()]
        query = HelpDeskTicket.query.filter(
            HelpDeskTicket.category_id.in_(cat_ids)
        )
    elif user.get("is_admin"):
        # Admin accessing staff panel sees all
        dept = "All"
        query = HelpDeskTicket.query
    else:
        abort(403)

    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if priority_filter != "all":
        query = query.filter_by(priority=priority_filter)

    tickets = query.order_by(HelpDeskTicket.updated_at.desc()).all()
    return render_template(
        "helpdesk/staff/dashboard.html",
        tickets=tickets,
        department=dept if staff else "All",
        status_filter=status_filter,
        priority_filter=priority_filter,
        current_staff=staff,
    )


@helpdesk_bp.route("/helpdesk/staff/ticket/<int:id>/reply", methods=["POST"])
@login_required
@helpdesk_staff_required
def staff_reply(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    user = session["user"]

    body = request.form.get("body", "").strip()
    if not body:
        flash("Reply cannot be empty.", "error")
        return redirect(url_for("helpdesk.ticket_detail", id=id))

    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_username=user["username"],
        sender_name=user["full_name"],
        sender_name_ar=user.get("full_name_ar", ""),
        body=body,
        is_staff_reply=True,
    )
    db.session.add(msg)

    # If in_progress, keep; if open set to in_progress
    if ticket.status == "open":
        ticket.status = "in_progress"

    link = url_for("helpdesk.ticket_detail", id=ticket.id, _external=False)
    notify(
        recipient=ticket.created_by_username,
        title=f"Staff replied to {ticket.ticket_number}",
        title_ar=f"رد الدعم على {ticket.ticket_number}",
        body=body[:120],
        body_ar=body[:120],
        link=link,
    )

    db.session.commit()
    flash("Reply sent." if not _ar() else "تم إرسال الرد.", "success")
    return redirect(url_for("helpdesk.ticket_detail", id=id))


@helpdesk_bp.route("/helpdesk/staff/ticket/<int:id>/status", methods=["POST"])
@login_required
@helpdesk_staff_required
def staff_change_status(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    new_status = request.form.get("status", "").strip()
    valid = {"open", "in_progress", "resolved", "closed"}
    if new_status not in valid:
        flash("Invalid status.", "error")
        return redirect(url_for("helpdesk.ticket_detail", id=id))

    ticket.status = new_status
    link = url_for("helpdesk.ticket_detail", id=ticket.id, _external=False)
    notify(
        recipient=ticket.created_by_username,
        title=f"Ticket {ticket.ticket_number} status updated to {new_status.replace('_', ' ').title()}",
        title_ar=f"تم تحديث حالة التذكرة {ticket.ticket_number}",
        body=f"Status changed to: {new_status.replace('_', ' ')}",
        body_ar=f"تم تغيير الحالة إلى: {new_status}",
        link=link,
    )
    db.session.commit()
    flash(f"Status updated to {new_status.replace('_', ' ')}.", "success")
    return redirect(url_for("helpdesk.ticket_detail", id=id))


@helpdesk_bp.route("/helpdesk/staff/ticket/<int:id>/priority", methods=["POST"])
@login_required
@helpdesk_staff_required
def staff_change_priority(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    new_priority = request.form.get("priority", "").strip()
    valid = {"low", "normal", "high", "urgent"}
    if new_priority not in valid:
        flash("Invalid priority.", "error")
        return redirect(url_for("helpdesk.ticket_detail", id=id))

    ticket.priority = new_priority
    db.session.commit()
    flash(f"Priority updated to {new_priority}.", "success")
    return redirect(url_for("helpdesk.ticket_detail", id=id))


@helpdesk_bp.route("/helpdesk/staff/ticket/<int:id>/assign", methods=["POST"])
@login_required
@helpdesk_staff_required
def staff_assign(id):
    ticket = HelpDeskTicket.query.get_or_404(id)
    user = session["user"]
    ticket.assigned_to_username = user["username"]
    if ticket.status == "open":
        ticket.status = "in_progress"
    db.session.commit()
    flash("Ticket assigned to you.", "success")
    return redirect(url_for("helpdesk.ticket_detail", id=id))


# ─── Admin Routes ─────────────────────────────────────────────────────────────

@helpdesk_bp.route("/admin/helpdesk")
@login_required
@admin_required
def admin_dashboard():
    status_filter = request.args.get("status", "all")
    priority_filter = request.args.get("priority", "all")
    dept_filter = request.args.get("department", "all")

    query = HelpDeskTicket.query
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if priority_filter != "all":
        query = query.filter_by(priority=priority_filter)
    if dept_filter != "all":
        cat_ids = [c.id for c in HelpDeskCategory.query.filter_by(
            department=dept_filter).all()]
        query = query.filter(HelpDeskTicket.category_id.in_(cat_ids))

    tickets = query.order_by(HelpDeskTicket.updated_at.desc()).all()

    # Get unique departments from categories
    departments = db.session.query(HelpDeskCategory.department).distinct().all()
    departments = [d[0] for d in departments]

    return render_template(
        "helpdesk/admin/dashboard.html",
        tickets=tickets,
        status_filter=status_filter,
        priority_filter=priority_filter,
        dept_filter=dept_filter,
        departments=departments,
    )


@helpdesk_bp.route("/admin/helpdesk/categories", methods=["GET", "POST"])
@login_required
@admin_required
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        if not name or not department:
            flash("Name and department are required.", "error")
        else:
            cat = HelpDeskCategory(
                name=name,
                name_ar=request.form.get("name_ar", "").strip(),
                department=department,
                department_ar=request.form.get("department_ar", "").strip(),
            )
            db.session.add(cat)
            db.session.commit()
            flash(f"Category '{name}' added.", "success")
        return redirect(url_for("helpdesk.admin_categories"))

    categories = HelpDeskCategory.query.order_by(HelpDeskCategory.name).all()
    return render_template("helpdesk/admin/categories.html", categories=categories)


@helpdesk_bp.route("/admin/helpdesk/categories/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_category(id):
    cat = HelpDeskCategory.query.get_or_404(id)
    if request.method == "POST":
        cat.name = request.form.get("name", cat.name).strip()
        cat.name_ar = request.form.get("name_ar", cat.name_ar).strip()
        cat.department = request.form.get("department", cat.department).strip()
        cat.department_ar = request.form.get("department_ar", cat.department_ar).strip()
        db.session.commit()
        flash(f"Category '{cat.name}' updated.", "success")
        return redirect(url_for("helpdesk.admin_categories"))
    return render_template("helpdesk/admin/category_form.html", cat=cat)


@helpdesk_bp.route("/admin/helpdesk/categories/<int:id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_category(id):
    cat = HelpDeskCategory.query.get_or_404(id)
    cat.is_active = not cat.is_active
    db.session.commit()
    state = "activated" if cat.is_active else "deactivated"
    flash(f"Category '{cat.name}' {state}.", "success")
    return redirect(url_for("helpdesk.admin_categories"))


@helpdesk_bp.route("/admin/helpdesk/staff")
@login_required
@admin_required
def admin_staff():
    staff_members = HelpDeskStaff.query.order_by(HelpDeskStaff.full_name).all()
    # Departments from active categories only (no free text)
    depts = db.session.query(HelpDeskCategory.department).filter_by(
        is_active=True
    ).distinct().order_by(HelpDeskCategory.department).all()
    departments = [d[0] for d in depts]
    return render_template(
        "helpdesk/admin/staff_members.html",
        staff_members=staff_members,
        departments=departments,
    )


@helpdesk_bp.route("/admin/helpdesk/staff/add", methods=["POST"])
@login_required
@admin_required
def admin_add_staff():
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    department = request.form.get("department", "").strip()

    if not username or not full_name or not department:
        flash("Username, name, and department are required.", "error")
        return redirect(url_for("helpdesk.admin_staff"))

    existing = HelpDeskStaff.query.filter_by(username=username).first()
    if existing:
        existing.is_active = True
        existing.full_name = full_name
        existing.department = department
        existing.full_name_ar = request.form.get("full_name_ar", "").strip()
        db.session.commit()
        flash(f"Staff member '{username}' reactivated/updated.", "success")
    else:
        staff = HelpDeskStaff(
            username=username,
            full_name=full_name,
            full_name_ar=request.form.get("full_name_ar", "").strip(),
            department=department,
        )
        db.session.add(staff)
        db.session.commit()
        flash(f"Staff member '{username}' added.", "success")

    return redirect(url_for("helpdesk.admin_staff"))


@helpdesk_bp.route("/admin/helpdesk/staff/<int:id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_staff(id):
    staff = HelpDeskStaff.query.get_or_404(id)
    staff.is_active = not staff.is_active
    db.session.commit()
    state = "activated" if staff.is_active else "deactivated"
    flash(f"Staff member '{staff.username}' {state}.", "success")
    return redirect(url_for("helpdesk.admin_staff"))


# ─── Report Routes ───────────────────────────────────────────────────────────

@helpdesk_bp.route("/admin/helpdesk/reports")
@login_required
@admin_required
def admin_reports():
    from datetime import datetime, timedelta

    report_type  = request.args.get("type", "category")
    selected_id  = request.args.get("selected_id", "all")
    date_from    = request.args.get("date_from", "")
    date_to      = request.args.get("date_to", "")
    status_filter   = request.args.get("status", "all")
    priority_filter = request.args.get("priority", "all")

    # Selector lists
    categories = HelpDeskCategory.query.order_by(HelpDeskCategory.name).all()
    staff_members = HelpDeskStaff.query.order_by(HelpDeskStaff.full_name).all()

    # Unique requesters — PostgreSQL requires DISTINCT ON column to lead ORDER BY
    from sqlalchemy import text
    requester_rows = db.session.execute(text(
        "SELECT DISTINCT ON (created_by_username) created_by_username, created_by_name "
        "FROM helpdesk_tickets ORDER BY created_by_username ASC"
    )).fetchall()
    requester_rows = sorted(requester_rows, key=lambda r: r.created_by_name)

    query = HelpDeskTicket.query

    # Type filter
    report_title = ""
    if report_type == "category":
        if selected_id != "all":
            query = query.filter_by(category_id=int(selected_id))
            cat = HelpDeskCategory.query.get(int(selected_id))
            report_title = cat.name if cat else selected_id
        else:
            report_title = "All Categories"
    elif report_type == "requester":
        if selected_id != "all":
            query = query.filter_by(created_by_username=selected_id)
            match = [r for r in requester_rows if r.created_by_username == selected_id]
            report_title = match[0].created_by_name if match else selected_id
        else:
            report_title = "All Requesters"
    elif report_type == "staff":
        if selected_id != "all":
            query = query.filter_by(assigned_to_username=selected_id)
            s = HelpDeskStaff.query.filter_by(username=selected_id).first()
            report_title = s.full_name if s else selected_id
        else:
            report_title = "All Staff"

    # Status / priority filters
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if priority_filter != "all":
        query = query.filter_by(priority=priority_filter)

    # Date filters (on created_at)
    if date_from:
        try:
            query = query.filter(
                HelpDeskTicket.created_at >= datetime.strptime(date_from, "%Y-%m-%d")
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                HelpDeskTicket.created_at <=
                datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            )
        except ValueError:
            pass

    tickets = query.order_by(HelpDeskTicket.created_at.desc()).all()

    return render_template(
        "helpdesk/admin/reports.html",
        tickets=tickets,
        report_type=report_type,
        selected_id=selected_id,
        date_from=date_from,
        date_to=date_to,
        status_filter=status_filter,
        priority_filter=priority_filter,
        report_title=report_title,
        categories=categories,
        staff_members=staff_members,
        requester_rows=requester_rows,
    )


@helpdesk_bp.route("/admin/helpdesk/reports/print")
@login_required
@admin_required
def admin_reports_print():
    from datetime import datetime, timedelta

    report_type     = request.args.get("type", "category")
    selected_id     = request.args.get("selected_id", "all")
    date_from       = request.args.get("date_from", "")
    date_to         = request.args.get("date_to", "")
    status_filter   = request.args.get("status", "all")
    priority_filter = request.args.get("priority", "all")

    from sqlalchemy import text
    requester_rows = db.session.execute(text(
        "SELECT DISTINCT ON (created_by_username) created_by_username, created_by_name "
        "FROM helpdesk_tickets ORDER BY created_by_username ASC"
    )).fetchall()

    query = HelpDeskTicket.query
    report_title = ""

    if report_type == "category":
        if selected_id != "all":
            query = query.filter_by(category_id=int(selected_id))
            cat = HelpDeskCategory.query.get(int(selected_id))
            report_title = cat.name if cat else selected_id
        else:
            report_title = "All Categories"
    elif report_type == "requester":
        if selected_id != "all":
            query = query.filter_by(created_by_username=selected_id)
            match = [r for r in requester_rows if r.created_by_username == selected_id]
            report_title = match[0].created_by_name if match else selected_id
        else:
            report_title = "All Requesters"
    elif report_type == "staff":
        if selected_id != "all":
            query = query.filter_by(assigned_to_username=selected_id)
            s = HelpDeskStaff.query.filter_by(username=selected_id).first()
            report_title = s.full_name if s else selected_id
        else:
            report_title = "All Staff"

    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    if priority_filter != "all":
        query = query.filter_by(priority=priority_filter)

    if date_from:
        try:
            query = query.filter(
                HelpDeskTicket.created_at >= datetime.strptime(date_from, "%Y-%m-%d")
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                HelpDeskTicket.created_at <=
                datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            )
        except ValueError:
            pass

    tickets = query.order_by(HelpDeskTicket.created_at.desc()).all()

    return render_template(
        "helpdesk/admin/report_print.html",
        tickets=tickets,
        report_type=report_type,
        selected_id=selected_id,
        date_from=date_from,
        date_to=date_to,
        status_filter=status_filter,
        priority_filter=priority_filter,
        report_title=report_title,
        now=datetime.utcnow(),
    )


# ─── Notification Routes ──────────────────────────────────────────────────────

@helpdesk_bp.route("/notifications")
@login_required
def notifications():
    user = session["user"]
    notifs = Notification.query.filter_by(
        recipient_username=user["username"]
    ).order_by(Notification.created_at.desc()).all()
    return render_template("helpdesk/notifications.html", notifs=notifs)


@helpdesk_bp.route("/notifications/<int:id>/read", methods=["POST"])
@login_required
def mark_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.recipient_username != session["user"]["username"]:
        abort(403)
    notif.is_read = True
    db.session.commit()
    return redirect(url_for("helpdesk.notifications"))


@helpdesk_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    user = session["user"]
    Notification.query.filter_by(
        recipient_username=user["username"], is_read=False
    ).update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("helpdesk.notifications"))
