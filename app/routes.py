from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from . import db
from .auth import authenticate, get_managers
from .models import LeaveRequest, generate_request_number

main = Blueprint("main", __name__)

def _ar():
    from flask import request as _req
    return _req.form.get('ui_lang', session.get('lang', 'en')) == 'ar'

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
            flash(
                "غير مصرح. هذه الصفحة للمسؤولين فقط." if _ar()
                else "Access denied. Admin privileges required.",
                "error"
            )
            return redirect(url_for("cars.portal"))
        return f(*args, **kwargs)
    return decorated

def extract_form_data(form, user=None):
    lang = form.get("active_language", "en")
    return {
        "active_language": lang,
        "employee_name":       user["full_name"] if user else form.get("employee_name", ""),
        "employee_department": user.get("department", "") if user else form.get("employee_department", ""),
        "employee_number":     user.get("employee_number", "") if user else form.get("employee_number", ""),
        "reason":              form.get("reason", "").strip(),
        "destination":         form.get("destination", "").strip(),
        "manager_name":        form.get("manager_name", "").strip(),
        "employee_name_ar":       form.get("employee_name_ar", "").strip(),
        "employee_department_ar": form.get("employee_department_ar", "").strip(),
        "reason_ar":              form.get("reason_ar", "").strip(),
        "destination_ar":         form.get("destination_ar", "").strip(),
        "manager_name_ar":        form.get("manager_name_ar", "").strip(),
    }

@main.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("cars.portal"))
    error = None
    if request.method == "POST":
        user = authenticate(request.form["username"], request.form["password"])
        if user:
            session["user"] = user
            session.permanent = True
            return redirect(url_for("cars.portal"))
        error = (
            "اسم المستخدم أو كلمة المرور غير صحيحة." if _ar()
            else "Invalid username or password."
        )
    return render_template("login.html", error=error)

@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))

@main.route("/ping", methods=["POST"])
@login_required
def ping():
    from flask import jsonify
    return jsonify({"ok": True})

@main.route("/")
@login_required
def dashboard():
    user = session["user"]
    records = LeaveRequest.query.filter_by(
        employee_username=user["username"]
    ).order_by(LeaveRequest.created_at.desc()).all()
    return render_template("dashboard.html", user=user, records=records)

@main.route("/leave/new", methods=["GET", "POST"])
@login_required
def new_leave():
    user = session["user"]
    managers = get_managers()
    if request.method == "POST":
        try:
            departure = datetime.strptime(request.form["departure_datetime"], "%Y-%m-%dT%H:%M")
            return_dt = datetime.strptime(request.form["return_datetime"], "%Y-%m-%dT%H:%M")
        except ValueError:
            flash(
                "صيغة التاريخ غير صحيحة." if _ar() else "Invalid date format.",
                "error"
            )
            return render_template("leave_form.html", user=user, managers=managers)

        if return_dt <= departure:
            flash(
                "يجب أن يكون وقت العودة بعد وقت المغادرة." if _ar()
                else "Return time must be after departure time.",
                "error"
            )
            return render_template("leave_form.html", user=user, managers=managers, form=request.form)

        data = extract_form_data(request.form, user=user)
        lang = data["active_language"]

        if lang == "en" and not data["reason"]:
            flash("Reason for leaving is required.", "error")
            return render_template("leave_form.html", user=user, managers=managers, form=request.form)
        if lang == "ar" and not data["reason_ar"]:
            flash("سبب المغادرة مطلوب.", "error")
            return render_template("leave_form.html", user=user, managers=managers, form=request.form)
        if not data["manager_name"]:
            flash(
                "يرجى اختيار المدير المعتمد." if _ar()
                else "Please select an approving manager.",
                "error"
            )
            return render_template("leave_form.html", user=user, managers=managers, form=request.form)

        lr = LeaveRequest(
            request_number=generate_request_number(),
            employee_username=user["username"],
            active_language=lang,
            employee_name=data["employee_name"],
            employee_department=data["employee_department"],
            employee_number=data["employee_number"],
            reason=data["reason"],
            destination=data["destination"],
            manager_name=data["manager_name"],
            employee_name_ar=data["employee_name_ar"],
            employee_department_ar=data["employee_department_ar"],
            reason_ar=data["reason_ar"],
            destination_ar=data["destination_ar"],
            manager_name_ar=data["manager_name_ar"],
            departure_datetime=departure,
            return_datetime=return_dt,
            status="draft",
        )
        db.session.add(lr)
        db.session.commit()

        if request.form.get("action") == "print":
            return redirect(url_for("main.print_slip", id=lr.id))
        flash(
            f"تم حفظ طلب المغادرة {lr.request_number}." if _ar()
            else f"Leave request {lr.request_number} saved.",
            "success"
        )
        return redirect(url_for("cars.portal"))

    return render_template("leave_form.html", user=user, managers=managers)

@main.route("/leave/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_leave(id):
    lr = LeaveRequest.query.get_or_404(id)
    user = session["user"]
    if lr.employee_username != user["username"] and not user.get("is_admin"):
        flash(
            "يمكنك تعديل طلباتك الخاصة فقط." if _ar()
            else "You can only edit your own requests.",
            "error"
        )
        return redirect(url_for("cars.portal"))
    if not lr.is_editable():
        flash(
            f"الطلب {lr.request_number} في حالة {lr.status} ولا يمكن تعديله." if _ar()
            else f"Request {lr.request_number} is {lr.status} and cannot be edited.",
            "error"
        )
        return redirect(url_for("cars.portal"))
    managers = get_managers()
    if request.method == "POST":
        try:
            departure = datetime.strptime(request.form["departure_datetime"], "%Y-%m-%dT%H:%M")
            return_dt = datetime.strptime(request.form["return_datetime"], "%Y-%m-%dT%H:%M")
        except ValueError:
            flash(
                "صيغة التاريخ غير صحيحة." if _ar() else "Invalid date format.",
                "error"
            )
            return render_template("leave_edit.html", lr=lr, user=user, managers=managers)
        if return_dt <= departure:
            flash(
                "يجب أن يكون وقت العودة بعد وقت المغادرة." if _ar()
                else "Return time must be after departure time.",
                "error"
            )
            return render_template("leave_edit.html", lr=lr, user=user, managers=managers)

        data = extract_form_data(request.form)
        lang = data["active_language"]

        if lang == "en" and not data["reason"]:
            flash("Reason for leaving is required.", "error")
            return render_template("leave_edit.html", lr=lr, user=user, managers=managers)
        if lang == "ar" and not data["reason_ar"]:
            flash("سبب المغادرة مطلوب.", "error")
            return render_template("leave_edit.html", lr=lr, user=user, managers=managers)
        if not data["manager_name"]:
            flash(
                "يرجى اختيار المدير المعتمد." if _ar()
                else "Please select an approving manager.",
                "error"
            )
            return render_template("leave_edit.html", lr=lr, user=user, managers=managers)

        lr.active_language        = lang
        lr.reason                 = data["reason"]
        lr.destination            = data["destination"]
        lr.manager_name           = data["manager_name"]
        lr.employee_name_ar       = data["employee_name_ar"]
        lr.employee_department_ar = data["employee_department_ar"]
        lr.reason_ar              = data["reason_ar"]
        lr.destination_ar         = data["destination_ar"]
        lr.manager_name_ar        = data["manager_name_ar"]
        lr.departure_datetime     = departure
        lr.return_datetime        = return_dt
        lr.updated_at             = datetime.utcnow()
        db.session.commit()

        if request.form.get("action") == "print":
            return redirect(url_for("main.print_slip", id=lr.id))
        flash(
            f"تم تحديث الطلب {lr.request_number}." if _ar()
            else f"Request {lr.request_number} updated.",
            "success"
        )
        return redirect(url_for("cars.portal"))

    return render_template("leave_edit.html", lr=lr, user=user, managers=managers)

@main.route("/leave/<int:id>/print")
@login_required
def print_slip(id):
    lr = LeaveRequest.query.get_or_404(id)
    if lr.status == "draft":
        lr.status = "pending"
        lr.printed_at = datetime.utcnow()
        db.session.commit()
    return render_template("print_slip.html", lr=lr)

@main.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    status_filter = request.args.get("status", "all")
    query = LeaveRequest.query.order_by(LeaveRequest.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    records = query.all()
    return render_template("admin/dashboard.html", records=records,
                           user=session["user"], status_filter=status_filter)

@main.route("/admin/leave/<int:id>")
@login_required
@admin_required
def admin_view(id):
    lr = LeaveRequest.query.get_or_404(id)
    return render_template("admin/record_view.html", lr=lr, user=session["user"])

@main.route("/admin/leave/<int:id>/status", methods=["POST"])
@login_required
@admin_required
def update_status(id):
    lr = LeaveRequest.query.get_or_404(id)
    new_status = request.form.get("status")
    if new_status in ("draft", "pending", "approved", "archived"):
        lr.status = new_status
        db.session.commit()
        flash(
            f"تم تغيير حالة الطلب {lr.request_number} إلى {new_status}." if _ar()
            else f"Request {lr.request_number} marked as {new_status}.",
            "success"
        )
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/leave/reports")
@login_required
@admin_required
def admin_leave_reports():
    from sqlalchemy import text
    report_type   = request.args.get("type", "employee")
    selected_id   = request.args.get("selected_id", "all")
    date_from     = request.args.get("date_from", "")
    date_to       = request.args.get("date_to", "")
    status_filter = request.args.get("status", "all")

    # Distinct selectors
    employee_rows = db.session.execute(text(
        "SELECT DISTINCT ON (employee_name) "
        "employee_username, employee_name, employee_department, employee_name_ar "
        "FROM leave_requests ORDER BY employee_name ASC"
    )).fetchall()
    department_rows = db.session.execute(text(
        "SELECT DISTINCT employee_department, employee_department_ar "
        "FROM leave_requests "
        "WHERE employee_department IS NOT NULL AND employee_department != '' "
        "ORDER BY employee_department ASC"
    )).fetchall()
    manager_rows = db.session.execute(text(
        "SELECT DISTINCT manager_name, manager_name_ar "
        "FROM leave_requests "
        "WHERE manager_name IS NOT NULL AND manager_name != '' "
        "ORDER BY manager_name ASC"
    )).fetchall()

    query = LeaveRequest.query

    if report_type == "employee" and selected_id != "all":
        query = query.filter_by(employee_username=selected_id)
    elif report_type == "department" and selected_id != "all":
        query = query.filter(LeaveRequest.employee_department == selected_id)
    elif report_type == "manager" and selected_id != "all":
        query = query.filter(LeaveRequest.manager_name == selected_id)

    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    if date_from:
        try:
            query = query.filter(LeaveRequest.departure_datetime >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(LeaveRequest.departure_datetime <= datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    records = query.order_by(LeaveRequest.departure_datetime.desc()).all()

    # Stats
    durations = [(r.return_datetime - r.departure_datetime).total_seconds() / 86400 for r in records]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0
    stats = {
        "total":    len(records),
        "approved": sum(1 for r in records if r.status == "approved"),
        "pending":  sum(1 for r in records if r.status == "pending"),
        "draft":    sum(1 for r in records if r.status == "draft"),
        "archived": sum(1 for r in records if r.status == "archived"),
        "avg_duration": avg_duration,
    }

    # Report title
    if report_type == "employee":
        if selected_id != "all" and records:
            report_title = f"{records[0].employee_name} ({selected_id})"
        elif selected_id != "all":
            match = [u for u in employee_rows if u.employee_username == selected_id]
            report_title = match[0].employee_name if match else selected_id
        else:
            report_title = "All Employees"
    elif report_type == "department":
        report_title = selected_id if selected_id != "all" else "All Departments"
    else:
        report_title = selected_id if selected_id != "all" else "All Managers"

    return render_template("admin/reports.html",
        employee_rows=employee_rows, department_rows=department_rows,
        manager_rows=manager_rows, records=records,
        report_type=report_type, selected_id=selected_id,
        date_from=date_from, date_to=date_to,
        status_filter=status_filter, report_title=report_title, stats=stats)


@main.route("/admin/leave/reports/print")
@login_required
@admin_required
def admin_leave_reports_print():
    from sqlalchemy import text
    report_type   = request.args.get("type", "employee")
    selected_id   = request.args.get("selected_id", "all")
    date_from     = request.args.get("date_from", "")
    date_to       = request.args.get("date_to", "")
    status_filter = request.args.get("status", "all")

    query = LeaveRequest.query

    if report_type == "employee" and selected_id != "all":
        query = query.filter_by(employee_username=selected_id)
    elif report_type == "department" and selected_id != "all":
        query = query.filter(LeaveRequest.employee_department == selected_id)
    elif report_type == "manager" and selected_id != "all":
        query = query.filter(LeaveRequest.manager_name == selected_id)

    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    if date_from:
        try:
            query = query.filter(LeaveRequest.departure_datetime >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(LeaveRequest.departure_datetime <= datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    records = query.order_by(LeaveRequest.departure_datetime.desc()).all()

    durations = [(r.return_datetime - r.departure_datetime).total_seconds() / 86400 for r in records]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0
    stats = {
        "total":    len(records),
        "approved": sum(1 for r in records if r.status == "approved"),
        "pending":  sum(1 for r in records if r.status == "pending"),
        "draft":    sum(1 for r in records if r.status == "draft"),
        "archived": sum(1 for r in records if r.status == "archived"),
        "avg_duration": avg_duration,
    }

    if report_type == "employee":
        if selected_id != "all" and records:
            report_title = f"{records[0].employee_name}"
        else:
            report_title = "All Employees"
    elif report_type == "department":
        report_title = selected_id if selected_id != "all" else "All Departments"
    else:
        report_title = selected_id if selected_id != "all" else "All Managers"

    return render_template("admin/report_print.html",
        records=records, report_type=report_type, selected_id=selected_id,
        date_from=date_from, date_to=date_to, status_filter=status_filter,
        report_title=report_title, stats=stats, now=datetime.utcnow())


@main.route("/set-language/<lang>")
def set_language(lang):
    if lang in ("en", "ar"):
        session["lang"] = lang
    return redirect(request.referrer or url_for("main.login"))
