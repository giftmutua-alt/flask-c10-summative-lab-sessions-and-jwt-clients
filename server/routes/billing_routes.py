from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.benson.models import User, Patient
from ..services import billing_service, report_service, matching_service

billing_bp = Blueprint("billing", __name__)


# if a service raises one of these errors, send a JSON message back
@billing_bp.errorhandler(ValueError)
def handle_bad_input(error):
    return jsonify({"success": False, "message": str(error)}), 400


@billing_bp.errorhandler(LookupError)
def handle_not_found(error):
    return jsonify({"success": False, "message": str(error)}), 404


def get_current_user():
    return User.query.get(int(get_jwt_identity()))


def is_staff(user):
    return user.role in ["admin", "billing"]


def get_my_patient(user):
    return Patient.query.filter_by(user_id=user.id).first()


def forbidden():
    return jsonify({"success": False, "message": "You are not allowed to do this"}), 403


# ---------------- INVOICES ----------------

@billing_bp.route("/api/billing/invoices", methods=["POST"])
@jwt_required()
def create_invoice():
    user = get_current_user()
    if not is_staff(user):
        return forbidden()

    data = request.get_json() or {}
    invoice = billing_service.create_invoice(
        patient_id=data.get("patient_id"),
        items=data.get("items"),
        tax_rate=data.get("tax_rate", 0),
        discount=data.get("discount", 0),
        created_by=user.id,
    )
    return jsonify({"success": True, "message": "Invoice created", "data": invoice}), 201


@billing_bp.route("/api/billing/invoices", methods=["GET"])
@jwt_required()
def list_invoices():
    user = get_current_user()
    patient_id = request.args.get("patient_id", type=int)

    # a patient can only see their own invoices
    if not is_staff(user):
        my_patient = get_my_patient(user)
        if my_patient is None:
            return forbidden()
        patient_id = my_patient.id

    invoices = billing_service.list_invoices(patient_id, request.args.get("status"))
    return jsonify({"success": True, "data": invoices}), 200


@billing_bp.route("/api/billing/invoices/<int:invoice_id>", methods=["GET"])
@jwt_required()
def get_invoice(invoice_id):
    user = get_current_user()
    invoice = billing_service.get_invoice(invoice_id)

    if not is_staff(user):
        my_patient = get_my_patient(user)
        if my_patient is None or my_patient.id != invoice.patient_id:
            return forbidden()

    return jsonify({"success": True, "data": billing_service.invoice_to_dict(invoice)}), 200


@billing_bp.route("/api/billing/invoices/<int:invoice_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_invoice(invoice_id):
    user = get_current_user()
    if not is_staff(user):
        return forbidden()

    invoice = billing_service.cancel_invoice(invoice_id)
    return jsonify({"success": True, "message": "Invoice cancelled", "data": invoice}), 200


# ---------------- PAYMENTS ----------------

@billing_bp.route("/api/billing/invoices/<int:invoice_id>/payments", methods=["POST"])
@jwt_required()
def record_payment(invoice_id):
    user = get_current_user()
    if not is_staff(user):
        return forbidden()

    data = request.get_json() or {}
    invoice = billing_service.record_payment(
        invoice_id=invoice_id,
        amount=data.get("amount"),
        method=data.get("method"),
        reference=data.get("reference"),
        received_by=user.id,
    )
    return jsonify({"success": True, "message": "Payment recorded", "data": invoice}), 201


# ---------------- BALANCES ----------------

@billing_bp.route("/api/billing/patients/<int:patient_id>/balance", methods=["GET"])
@jwt_required()
def patient_balance(patient_id):
    user = get_current_user()

    if not is_staff(user):
        my_patient = get_my_patient(user)
        if my_patient is None or my_patient.id != patient_id:
            return forbidden()

    balance = billing_service.get_patient_balance(patient_id)
    return jsonify({"success": True, "data": balance}), 200


@billing_bp.route("/api/billing/outstanding", methods=["GET"])
@jwt_required()
def outstanding():
    if not is_staff(get_current_user()):
        return forbidden()

    return jsonify({"success": True, "data": billing_service.list_outstanding()}), 200


# ---------------- REPORTS ----------------

@billing_bp.route("/api/reports/revenue", methods=["GET"])
@jwt_required()
def revenue_report():
    if not is_staff(get_current_user()):
        return forbidden()

    report = report_service.revenue_report(request.args.get("start"), request.args.get("end"))
    return jsonify({"success": True, "data": report}), 200


@billing_bp.route("/api/reports/payments", methods=["GET"])
@jwt_required()
def payment_report():
    if not is_staff(get_current_user()):
        return forbidden()

    report = report_service.payment_report(request.args.get("start"), request.args.get("end"))
    return jsonify({"success": True, "data": report}), 200


# ---------------- MATCHING ----------------

@billing_bp.route("/api/matching/doctors", methods=["GET"])
@jwt_required()
def match_doctors():
    doctors = matching_service.find_doctors(request.args.get("specialty"), request.args.get("date"))
    return jsonify({"success": True, "data": doctors}), 200