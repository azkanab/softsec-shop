import time
from datetime import datetime, timezone
import json
import base64
from flask import current_app
from pathlib import Path


from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
    jsonify,
    flash,
    current_app,
    send_file,
    Response
)

from flask_babel import lazy_gettext
from flask_login import current_user, login_required
from pluggy import HookimplMarker

from flaskshop.constant import OrderStatusKinds, PaymentStatusKinds, ShipStatusKinds, OrderReturnStatusKinds, RefundStatusKinds
from flaskshop.extensions import csrf_protect
from .payment import zhifubao
from .payment import paypal
from .shipping import dhl

from .models import Order, OrderPayment, OrderReturn, OrderRefund

impl = HookimplMarker("flaskshop")


@login_required
def index():
    return redirect(url_for("account.index"))


@login_required
def show(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, lazy_gettext("This is not your order!"))
    return render_template("orders/details.html", order=order)


def create_payment(token, payment_method):
    order = Order.query.filter_by(token=token).first()
    if order.status != OrderStatusKinds.unfulfilled.value:
        abort(403, lazy_gettext("This Order Can Not Pay"))
    payment_no = str(int(time.time())) + str(current_user.id)
    customer_ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    payment = OrderPayment.query.filter_by(order_id=order.id).first()
    if payment:
        payment.update(
            payment_method=payment_method,
            payment_no=payment_no,
            customer_ip_address=customer_ip_address,
        )
    else:
        payment = OrderPayment.create(
            order_id=order.id,
            payment_method=payment_method,
            payment_no=payment_no,
            status=PaymentStatusKinds.waiting.value,
            total=order.total,
            customer_ip_address=customer_ip_address,
        )
    # Task 3.5 Step 1: Calling function in Paypal to call Paypal REST API
    if payment_method == "paypal":
        response = paypal.create_order(order.total)
        response_json = response.get_data(as_text=True)
        success = response.status_code == 200
        if success:
            response_data = json.loads(response_json)
            # Task 3.5 Step 1: Set payment_no in the database with the payment ID generated from Paypal REST API
            payment.set_payment_no(response_data["id"])
            payment.save()
            return response
        else:
            return Response({"error": "Failed to create PayPal payment"}, status=400)
    elif payment_method == "alipay":
        redirect_url = zhifubao.send_order(order.token, payment_no, order.total)
        payment.redirect_url = redirect_url
    return payment


@login_required
def ali_pay(token):
    payment = create_payment(token, "alipay")
    return redirect(payment.redirect_url)

# Task 3.5 Step 1: Our API proxy to eventually call Paypal REST API to create order/payment
@login_required
def paypal_pay(token):
    response = create_payment(token, "paypal")
    return response

# Task 3.5 Step 2: Our API proxy to eventually call Paypal REST API to capture or finalize order/payment
def paypal_notify(payment_id):
    response = paypal.capture_order(payment_id)
    success = response.status_code == 200
    if success:
        response_data = json.loads(response.get_data(as_text=True))
        completed = response_data.get("status") == "COMPLETED"
        if completed:
            order_payment = OrderPayment.query.filter_by(
                payment_no=payment_id
            ).first()
            paid_time = datetime.strptime(response_data.get("create_time"), "%Y-%m-%dT%H:%M:%SZ")
            order_payment.pay_success(paid_at=paid_time)
            response_data["redirect_url"] = url_for("order.payment_success", _external=True)
            return jsonify(response_data), 200
    order_payment.update(
        status=PaymentStatusKinds.rejected.value
    )
    return response, 400

@csrf_protect.exempt
def ali_notify():
    data = request.form.to_dict()
    success = zhifubao.verify_order(data)
    if success:
        order_payment = OrderPayment.query.filter_by(
            payment_no=data["out_trade_no"]
        ).first()
        order_payment.pay_success(paid_at=data["gmt_payment"])
        return "SUCCESS"
    return "ERROR HAPPEND"


@login_required
def test_pay_flow(token):
    payment = create_payment(token, "testpay")
    payment.pay_success(paid_at=datetime.now())
    return redirect(url_for("order.payment_success"))


@login_required
def payment_success():
    payment_no = request.args.get("out_trade_no")
    if payment_no:
        res = zhifubao.query_order(payment_no)
        if res["code"] == "10000":
            order_payment = OrderPayment.query.filter_by(
                payment_no=res["out_trade_no"]
            ).first()
            order_payment.pay_success(paid_at=res["send_pay_date"])
        else:
            print(res["msg"])

    return render_template("orders/checkout_success.html")


@login_required
def cancel_order(token, is_refund):
    is_refund = bool(is_refund)
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, "This is not your order!")
    order.cancel()
    if is_refund:
        handle_refund(token)
    else:
        flash(lazy_gettext("Your order has been cancelled"), "success")
    return render_template("orders/details.html", order=order)

# Task 3.6. Decode base 64 from DHL response to a file
def decode_base_64(b64, type, order_token):
    
    shipping_label_dir = Path(current_app.static_folder) / "shipping_label"
    shipping_label_dir.mkdir(parents=True, exist_ok=True)
    
    bytes = base64.b64decode(b64)
    
    if type == "pdf":
        filename = f"{order_token}.pdf"
    else:
        filename = f"{order_token}.png"
    
    local_path = shipping_label_dir / filename
    
    with open(local_path, "wb") as f:
        f.write(bytes)
    
    return f"/static/shipping_label/{filename}"

# Task 3.6. Create a DHL Shipping Label for return an order and save it in folder /static/shipping_label
def generate_shipping_label(order):

    response = dhl.get_dhl_return_shipping_label(order)

    data = response.json()

    # Task 3.6. Processing PDF file
    pdf_url = None
    if "label" in data and "b64" in data["label"]:
        pdf_url = decode_base_64(data["label"]["b64"], "pdf", order.token)
    
    # Task 3.6. Processing PNG File
    qr_png_url = None
    if "qrLabel" in data and "b64" in data["qrLabel"]:
        qr_png_url = decode_base_64(data["qrLabel"]["b64"], "png", order.token)

    return qr_png_url, pdf_url

# Task 3.6. - TO DO: PayPal refund
@login_required
def paypal_refund(order):
    """
    The Manager's Script:
    1. Find the payment paper in our filing cabinet (Database).
    2. Check if they actually paid with PayPal.
    3. Use the 'paypal.py' phone to call the bank and ask for a refund.
    """
    # 1. Retrieve the payment info from database
    payment = OrderPayment.query.filter_by(order_id=order.id).first()
    
    if not payment:
        flash("Error: Payment record missing.", "warning")
        return False
        
    # 2. Verify it is a PayPal transaction
    if payment.payment_method != "paypal":
        flash("Error: This is not a PayPal order.", "warning")
        return False

    # 3. Call the refund function we wrote in Step 1
    # payment.payment_no is the 'Order ID' we saved when they bought the item.
    try:
        response = paypal.refund_order(payment.payment_no, order.total)
    except Exception as e:
        print(f"Critical Error calling PayPal: {e}")
        return False

    # 4. Read the answer from PayPal
    # Status 201 means "Created" (Refund started), 200 means "OK".
    if response.status_code in (200, 201):
        try:
            # We convert the text answer into a Python Dictionary
            data = json.loads(response.get_data(as_text=True))
            
            # If the status is 'COMPLETED' or 'PROCESSING', we succeeded!
            if data.get("status") in ["COMPLETED", "PROCESSING"]:
                return True
        except Exception:
            # If we can't read the details but the code was Good (200/201), trust it worked.
            return True
            
    # If we get here, the refund failed
    flash("PayPal refused the refund. Please check logs.", "error")
    return False

@login_required
def handle_refund(token):
    order = Order.query.filter_by(token=token).first()
    payment = OrderPayment.query.filter_by(order_id=order.id).first()
    customer_ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    payment_no = str(int(time.time())) + str(current_user.id)

    # Task 3.6. - Create new row for order_refund table
    refund = OrderRefund.query.filter_by(order_id=order.id).first()
    if not refund:
        refund = OrderRefund.create(
            order_id=order.id,
            status=RefundStatusKinds.waiting.value,
            total=payment.total,
            customer_ip_address=customer_ip_address,
            payment_method=payment.payment_method,
            payment_no=payment_no
        )

    # Task 3.6. - Handle refund process for each payment method
    refund_success = True
    if payment.payment_method == "paypal":
        refund_success = paypal_refund(order)
    else:
        pass # Can make a new function to handle other payment methods (if there is any)
    if refund_success:
        refund.update(
            status=RefundStatusKinds.confirmed.value,
            refunded_at=datetime.now(timezone.utc)
        )
        order.update(
            status=OrderStatusKinds.refunded.value
        )
        flash(lazy_gettext("Refund processed successfully"), "success")
    else:
        refund.update(
            status=RefundStatusKinds.rejected.value
        )
        flash(lazy_gettext("Refund process failed. Please wait for several more hours"), "warning")
    
    return redirect(url_for("dashboard.order_detail", id=order.id))

@login_required
def cancel_return_order(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, "This is not your order!")

    # Task 3.6. - Set status in order_order table to canceled and status in order_event table to order_canceled
    order.cancel()

    shipping_qr_url, shipping_label_url = generate_shipping_label(order)

    # Task 3.6. - Create a new row for OrderReturn
    returnOrder = OrderReturn.query.filter_by(order_id=order.id).first()
    if not returnOrder:
        returnOrder = OrderReturn.create(
            order_id=order.id,
            status=OrderReturnStatusKinds.label_created.value,
            shipping_label=shipping_label_url,
            cancellation_time=datetime.now(timezone.utc),
            carrier="DHL"
        )

    return jsonify({
        "success": True,
        "shipping_label_url": shipping_qr_url,
        "order_token": order.token,
        "cancellation_time": returnOrder.cancellation_time
    })

@login_required
def send_return(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, "This is not your order!")

    # Task 3.6. - Update the status in order_return table
    returnOrder = OrderReturn.query.filter_by(order_id=order.id).first()
    if returnOrder:
        returnOrder.update(
            status=OrderReturnStatusKinds.in_transit.value
        )
    else:
        return jsonify({
            "success": False,
            "message": "Data not found in the table"
        })
    
    # ---- IMPORTANT ----
    # Get the PDF LOCAL PATH saved earlier
    pdf_url = returnOrder.shipping_label

    if not pdf_url:
        return jsonify({
            "success": False,
            "message": "Shipping label not generated yet"
        })

    flash(lazy_gettext("Your return will be picked up soon. Do not lose the shipping label and please attach it to your package"), "success")

    order.update(
        status=OrderStatusKinds.returned.value
    )

    return jsonify({
        "success": True,
        "message": "The status is already updated",
        "pdf_url": pdf_url
    })

@login_required
def receive_return(token):
    order = Order.query.filter_by(token=token).first()
    if not order:
        abort(404, "Order not found")

    # Task 3.6. - Update the status in order_return table
    returnOrder = OrderReturn.query.filter_by(order_id=order.id).first()
    if returnOrder:
        returnOrder.update(
            status=OrderReturnStatusKinds.received.value,
            arrival_time=datetime.now(timezone.utc)
        )
    else:
        flash(lazy_gettext("Return record not found"), "error")
        return redirect(url_for("dashboard.order_detail", id=order.id))

    handle_refund(token)

    return redirect(url_for("dashboard.order_detail", id=order.id))


@login_required
def receive(token):
    order = Order.query.filter_by(token=token).first()
    order.update(
        status=OrderStatusKinds.completed.value,
        ship_status=ShipStatusKinds.received.value,
    )
    return render_template("orders/details.html", order=order)

@login_required
def download_shipping_label(filename):

    pdf_path = Path(current_app.static_folder) / "shipping_label" / filename

    if not pdf_path.exists():
        abort(404)

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("order", __name__)
    bp.add_url_rule("/", view_func=index)
    bp.add_url_rule("/<string:token>", view_func=show)
    bp.add_url_rule("/pay/<string:token>/alipay", view_func=ali_pay)
    # Task 3.5 Endpoints for step 1 & step 2 of Paypal Gateway
    bp.add_url_rule("/pay/<string:token>/paypal", view_func=paypal_pay, methods=["POST"])
    bp.add_url_rule("/paypal/gateway/<string:payment_id>/", view_func=paypal_notify, methods=["POST"])
    bp.add_url_rule("/alipay/notify", view_func=ali_notify, methods=["POST", "HEAD"])
    bp.add_url_rule("/pay/<string:token>/testpay", view_func=test_pay_flow)
    bp.add_url_rule("/payment_success", view_func=payment_success)
    bp.add_url_rule("/cancel/<string:token>/<int:is_refund>", view_func=cancel_order)
    bp.add_url_rule("/cancel_return/<string:token>", view_func=cancel_return_order, methods=["POST"])
    bp.add_url_rule("/send_return/<string:token>", view_func=send_return, methods=["POST"])
    bp.add_url_rule("/receive_return/<string:token>", view_func=receive_return, methods=["GET", "POST"])
    bp.add_url_rule("/refund/<string:token>", view_func=handle_refund, methods=["GET", "POST"])
    bp.add_url_rule("/receive/<string:token>", view_func=receive)
    bp.add_url_rule("/download/label/<string:filename>", view_func=download_shipping_label)

    app.register_blueprint(bp, url_prefix="/orders")
