import os
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from flask import (
    render_template, redirect, url_for, request,
    session, flash, current_app
)
from app import db
from app.auth import get_managers
from app.cars import cars_bp
from app.cars.models import Car, CarBooking, generate_booking_number

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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
            return redirect(url_for("cars.dashboard"))
        return f(*args, **kwargs)
    return decorated

def _ar():
    from flask import request as _req
    import sys
    lang_from_form = _req.form.get('ui_lang', 'NOT_IN_FORM')
    lang_from_session = session.get('lang', 'NOT_IN_SESSION')
    print(f"DEBUG _ar(): form ui_lang={lang_from_form}, session lang={lang_from_session}", file=sys.stderr)
    return _req.form.get('ui_lang', session.get('lang', 'en')) == 'ar'

def _parse_date(val):
    try:
        return datetime.strptime(val, "%Y-%m-%d").date() if val else None
    except ValueError:
        return None

def _get_car_states():
    states = {}
    active = CarBooking.query.filter(
        CarBooking.status.in_(["pending", "borrowed"])
    ).order_by(CarBooking.created_at.desc()).all()
    for b in active:
        if b.car_id not in states:
            states[b.car_id] = {
                "status": b.status,
                "borrower": b.employee_name,
                "last_borrower": "",
                "last_borrowed_date": "",
                "last_return_note": ""
            }
    returned = CarBooking.query.filter(
        CarBooking.status == "returned"
    ).order_by(CarBooking.actual_return.desc()).all()
    seen = set()
    for b in returned:
        if b.car_id not in seen:
            seen.add(b.car_id)
            last_date = b.actual_return.strftime("%d %b %Y, %I:%M %p") if b.actual_return else ""
            if b.car_id not in states:
                states[b.car_id] = {
                    "status": "free",
                    "borrower": "",
                    "last_borrower": b.employee_name,
                    "last_borrowed_date": last_date,
                    "last_return_note": b.return_note or ""
                }
            else:
                states[b.car_id]["last_borrower"] = b.employee_name
                states[b.car_id]["last_borrowed_date"] = last_date
                states[b.car_id]["last_return_note"] = b.return_note or ""
    return states


@cars_bp.route("/portal")
@login_required
def portal():
    return render_template("cars/portal.html")


@cars_bp.route("/cars")
@login_required
def dashboard():
    user = session["user"]
    bookings = CarBooking.query.filter_by(
        employee_username=user["username"]
    ).order_by(CarBooking.created_at.desc()).all()
    return render_template("cars/dashboard.html", bookings=bookings, user=user)


@cars_bp.route("/cars/new", methods=["GET", "POST"])
@login_required
def new_booking():
    from datetime import date
    user = session["user"]
    managers = get_managers()
    all_cars = Car.query.filter_by(is_active=True).all()
    car_states = _get_car_states()

    if request.method == "POST":
        try:
            planned_departure = datetime.strptime(
                request.form["planned_departure"], "%Y-%m-%dT%H:%M")
        except ValueError:
            flash(
                "صيغة التاريخ غير صحيحة." if _ar() else "Invalid date format.",
                "error"
            )
            return render_template("cars/booking_form.html",
                           user=user, managers=managers,
                           all_cars=all_cars, car_states=car_states,
                           today=date.today())

        car_id = request.form.get("car_id", "").strip()
        if not car_id:
            flash("Please select a vehicle.", "error")
            return render_template("cars/booking_form.html",
                           user=user, managers=managers,
                           all_cars=all_cars, car_states=car_states,
                           today=date.today())

        if car_states.get(int(car_id), {}).get("status") == "borrowed":
            flash("That vehicle is currently out. Please choose another.", "error")
            return render_template("cars/booking_form.html",
                           user=user, managers=managers,
                           all_cars=all_cars, car_states=car_states,
                           today=date.today())

        lang = request.form.get("active_language", "en")
        booking = CarBooking(
            booking_number=generate_booking_number(),
            car_id=int(car_id),
            employee_username=user["username"],
            employee_name=user["full_name"],
            employee_name_ar=request.form.get("employee_name_ar", "").strip(),
            employee_department=user.get("department", ""),
            employee_department_ar=request.form.get("employee_department_ar", "").strip(),
            employee_number=user.get("employee_number", ""),
            destination=request.form.get("destination", "").strip(),
            destination_ar=request.form.get("destination_ar", "").strip(),
            purpose=request.form.get("purpose", "").strip(),
            purpose_ar=request.form.get("purpose_ar", "").strip(),
            manager_name=request.form.get("manager_name", "").strip(),
            manager_name_ar=request.form.get("manager_name_ar", "").strip(),
            planned_departure=planned_departure,
            active_language=lang,
            status="pending",
        )
        db.session.add(booking)
        db.session.commit()
        flash(
            f"تم تقديم الحجز {booking.booking_number} بنجاح." if _ar()
            else f"Booking {booking.booking_number} submitted successfully.",
            "success"
        )
        return redirect(url_for("cars.dashboard"))

    return render_template("cars/booking_form.html",
                           user=user, managers=managers,
                           all_cars=all_cars, car_states=car_states,
                           today=date.today())


@cars_bp.route("/cars/booking/<int:id>")
@login_required
def booking_detail(id):
    booking = CarBooking.query.get_or_404(id)
    return render_template("cars/booking_detail.html", booking=booking)


@cars_bp.route("/admin/cars/bookings")
@login_required
@admin_required
def admin_bookings():
    status_filter = request.args.get("status", "all")
    query = CarBooking.query.order_by(CarBooking.created_at.desc())
    if status_filter != "all":
        query = query.filter_by(status=status_filter)
    bookings = query.all()
    return render_template("cars/admin/bookings.html",
                           bookings=bookings, status_filter=status_filter)


@cars_bp.route("/admin/cars/bookings/<int:id>/status", methods=["GET", "POST"])
@login_required
@admin_required
def admin_update_status(id):
    booking = CarBooking.query.get_or_404(id)

    if request.method == "POST":
        new_status = request.form.get("status")

        if new_status == "borrowed":
            actual_departure_str = request.form.get("actual_departure", "").strip()
            if actual_departure_str:
                try:
                    booking.actual_departure = datetime.strptime(
                        actual_departure_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    booking.actual_departure = datetime.utcnow()
            else:
                booking.actual_departure = datetime.utcnow()
            booking.status = "borrowed"
            db.session.commit()
            flash(
                f"تم تسليم المفتاح للحجز {booking.booking_number}." if _ar()
                else f"Booking {booking.booking_number} marked as borrowed. Key handed over.",
                "success"
            )
            return redirect(url_for("cars.admin_bookings"))

        elif new_status == "returned":
            odometer = request.form.get("odometer_return", "").strip()
            actual_return_str = request.form.get("actual_return", "").strip()
            if not odometer:
                flash("Please enter the odometer reading.", "error")
                return render_template("cars/admin/return_confirm.html", booking=booking)
            try:
                if actual_return_str:
                    actual_return_dt = datetime.strptime(actual_return_str, "%Y-%m-%dT%H:%M")
                else:
                    actual_return_dt = datetime.utcnow()
                if booking.actual_departure and actual_return_dt < booking.actual_departure:
                    flash(
                        f"وقت الإرجاع ({actual_return_dt.strftime('%d %b %Y %I:%M %p')}) لا يمكن أن يكون قبل وقت الاستعارة ({booking.actual_departure.strftime('%d %b %Y %I:%M %p')})." if _ar()
                        else f"Return time ({actual_return_dt.strftime('%d %b %Y %I:%M %p')}) cannot be earlier than borrow time ({booking.actual_departure.strftime('%d %b %Y %I:%M %p')}).",
                        "error"
                    )
                    return render_template("cars/admin/return_confirm.html", booking=booking)
                # Odometer must be >= last recorded mileage
                if booking.car.current_mileage and float(odometer) < booking.car.current_mileage:
                    flash(
                        f"قراءة العداد ({float(odometer):,.0f} كم) لا يمكن أن تكون أقل من آخر قراءة مسجلة ({booking.car.current_mileage:,.0f} كم)." if _ar()
                        else f"Odometer reading ({float(odometer):,.0f} km) cannot be less than last recorded reading ({booking.car.current_mileage:,.0f} km).",
                        "error"
                    )
                    return render_template("cars/admin/return_confirm.html", booking=booking)
                booking.odometer_return = float(odometer)
                booking.actual_return = actual_return_dt
                booking.return_note = request.form.get("return_note", "").strip()
                booking.status = "returned"
                booking.car.current_mileage = float(odometer)
                db.session.commit()
                flash(
                    f"تم تسجيل إرجاع الحجز {booking.booking_number} بنجاح." if _ar()
                    else f"Booking {booking.booking_number} returned successfully.",
                    "success"
                )
            except ValueError:
                flash("Invalid odometer or date value.", "error")
                return render_template("cars/admin/return_confirm.html", booking=booking)
            return redirect(url_for("cars.admin_bookings"))

        elif new_status == "archived":
            booking.status = "archived"
            db.session.commit()
            flash(
                f"تمت أرشفة الحجز {booking.booking_number}." if _ar()
                else f"Booking {booking.booking_number} archived.",
                "success"
            )
            return redirect(url_for("cars.admin_bookings"))

        elif new_status == "pending":
            booking.status = "pending"
            db.session.commit()
            flash(f"Booking {booking.booking_number} reset to pending.", "success")
            return redirect(url_for("cars.admin_bookings"))

    if booking.status == "borrowed":
        return render_template("cars/admin/return_confirm.html", booking=booking)
    return redirect(url_for("cars.admin_bookings"))


@cars_bp.route("/admin/cars/fleet")
@login_required
@admin_required
def admin_fleet():
    from datetime import date
    cars = Car.query.order_by(Car.created_at.desc()).all()
    car_states = _get_car_states()
    return render_template("cars/admin/fleet.html", cars=cars,
                           car_states=car_states, today=date.today())


@cars_bp.route("/admin/cars/fleet/new", methods=["GET", "POST"])
@login_required
@admin_required
def admin_add_car():
    if request.method == "POST":
        filename = ""
        if "plate_image" in request.files:
            file = request.files["plate_image"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(
                    current_app.root_path, "static", "uploads", "cars", filename)
                file.save(upload_path)
        mileage_val = request.form.get("current_mileage", "").strip()
        car = Car(
            plate_number=request.form["plate_number"].strip().upper(),
            plate_number_ar=request.form.get("plate_number_ar", "").strip(),
            make=request.form["make"].strip(),
            model=request.form["model"].strip(),
            year=int(request.form["year"]),
            color=request.form.get("color", "").strip(),
            color_ar=request.form.get("color_ar", "").strip(),
            seats=int(request.form.get("seats", 5)),
            plate_image=filename,
            is_active=True,
            current_mileage=float(mileage_val) if mileage_val else 0,
            last_major_maintenance=_parse_date(request.form.get("last_major_maintenance", "")),
            last_minor_maintenance=_parse_date(request.form.get("last_minor_maintenance", "")),
            registration_expiry=_parse_date(request.form.get("registration_expiry", "")),
        )
        db.session.add(car)
        db.session.commit()
        flash(
            f"تمت إضافة السيارة {car.plate_number} إلى الأسطول." if _ar()
            else f"Car {car.plate_number} added to fleet.",
            "success"
        )
        return redirect(url_for("cars.admin_fleet"))
    return render_template("cars/admin/car_form.html", car=None)


@cars_bp.route("/admin/cars/fleet/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_car(id):
    car = Car.query.get_or_404(id)
    if request.method == "POST":
        if "plate_image" in request.files:
            file = request.files["plate_image"]
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(
                    current_app.root_path, "static", "uploads", "cars", filename)
                file.save(upload_path)
                car.plate_image = filename
        mileage_val = request.form.get("current_mileage", "").strip()
        car.plate_number = request.form["plate_number"].strip().upper()
        car.plate_number_ar = request.form.get("plate_number_ar", "").strip()
        car.make = request.form["make"].strip()
        car.model = request.form["model"].strip()
        car.year = int(request.form["year"])
        car.color = request.form.get("color", "").strip()
        car.color_ar = request.form.get("color_ar", "").strip()
        car.seats = int(request.form.get("seats", 5))
        car.is_active = "is_active" in request.form
        car.current_mileage = float(mileage_val) if mileage_val else car.current_mileage
        car.last_major_maintenance = _parse_date(request.form.get("last_major_maintenance", ""))
        car.last_minor_maintenance = _parse_date(request.form.get("last_minor_maintenance", ""))
        car.registration_expiry = _parse_date(request.form.get("registration_expiry", ""))
        db.session.commit()
        flash(
            f"تم تحديث بيانات السيارة {car.plate_number}." if _ar()
            else f"Car {car.plate_number} updated.",
            "success"
        )
        return redirect(url_for("cars.admin_fleet"))
    return render_template("cars/admin/car_form.html", car=car)


@cars_bp.route("/admin/cars/fleet/<int:id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_car(id):
    car = Car.query.get_or_404(id)
    car.is_active = not car.is_active
    db.session.commit()
    if _ar():
        state = "تم تفعيلها" if car.is_active else "تم إيقافها"
        flash(f"السيارة {car.plate_number} {state}.", "success")
    else:
        state = "activated" if car.is_active else "deactivated"
        flash(f"Car {car.plate_number} {state}.", "success")
    return redirect(url_for("cars.admin_fleet"))


@cars_bp.route("/admin/cars/reports")
@login_required
@admin_required
def admin_reports():
    report_type = request.args.get("type", "car")
    selected_id  = request.args.get("selected_id", "all")
    date_from    = request.args.get("date_from", "")
    date_to      = request.args.get("date_to", "")

    # All cars for selector
    cars = Car.query.order_by(Car.plate_number).all()

    # All unique employees who ever made a booking
    # PostgreSQL requires DISTINCT ON to match ORDER BY
    from sqlalchemy import text
    user_rows = db.session.execute(text(
        "SELECT DISTINCT ON (employee_name) employee_username, employee_name, employee_department "
        "FROM car_bookings ORDER BY employee_name ASC"
    )).fetchall()

    bookings = []
    report_title = ""

    query = CarBooking.query

    # --- Filter by type ---
    if report_type == "car":
        if selected_id and selected_id != "all":
            query = query.filter_by(car_id=int(selected_id))
            car = Car.query.get(int(selected_id))
            report_title = f"{car.year} {car.make} {car.model} — {car.plate_number}" if car else ""
        else:
            report_title = "All Vehicles"

    elif report_type == "user":
        if selected_id and selected_id != "all":
            query = query.filter_by(employee_username=selected_id)
            # get name from first result after filtering
        else:
            report_title = "All Employees"

    # --- Date filters ---
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(CarBooking.planned_departure >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.filter(CarBooking.planned_departure <= dt + timedelta(days=1))
        except ValueError:
            pass

    bookings = query.order_by(CarBooking.planned_departure.desc()).all()

    # Set title for specific user after query
    if report_type == "user" and selected_id != "all" and bookings:
        report_title = f"{bookings[0].employee_name} ({selected_id})"
    elif report_type == "user" and selected_id != "all":
        # no bookings found, try from user_rows
        match = [u for u in user_rows if u.employee_username == selected_id]
        report_title = match[0].employee_name if match else selected_id

    return render_template("cars/admin/reports.html",
                           cars=cars,
                           user_rows=user_rows,
                           bookings=bookings,
                           report_type=report_type,
                           selected_id=selected_id,
                           date_from=date_from,
                           date_to=date_to,
                           report_title=report_title)


@cars_bp.route("/admin/cars/reports/print")
@login_required
@admin_required
def admin_reports_print():
    from datetime import date, datetime as dt
    report_type = request.args.get("type", "car")
    selected_id  = request.args.get("selected_id", "all")
    date_from    = request.args.get("date_from", "")
    date_to      = request.args.get("date_to", "")

    cars     = Car.query.order_by(Car.plate_number).all()
    query    = CarBooking.query
    report_title = ""

    if report_type == "car":
        if selected_id and selected_id != "all":
            query = query.filter_by(car_id=int(selected_id))
            car = Car.query.get(int(selected_id))
            report_title = f"{car.year} {car.make} {car.model} — {car.plate_number}" if car else ""
        else:
            report_title = "All Vehicles"
    elif report_type == "user":
        if selected_id and selected_id != "all":
            query = query.filter_by(employee_username=selected_id)
        else:
            report_title = "All Employees"

    if date_from:
        try:
            query = query.filter(CarBooking.planned_departure >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(CarBooking.planned_departure <= datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    bookings = query.order_by(CarBooking.planned_departure.desc()).all()

    if report_type == "user" and selected_id != "all" and bookings:
        report_title = f"{bookings[0].employee_name}"

    return render_template("cars/admin/report_print.html",
                           bookings=bookings,
                           report_type=report_type,
                           selected_id=selected_id,
                           date_from=date_from,
                           date_to=date_to,
                           report_title=report_title,
                           now=datetime.utcnow())
