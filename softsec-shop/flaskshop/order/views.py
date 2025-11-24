import time
import random
from datetime import datetime, timezone
import json

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
    jsonify,
    flash
)

from flask_babel import lazy_gettext
from flask_login import current_user, login_required
from pluggy import HookimplMarker

from flaskshop.constant import OrderStatusKinds, PaymentStatusKinds, ShipStatusKinds, OrderReturnStatusKinds, RefundStatusKinds
from flaskshop.extensions import csrf_protect
from .payment import zhifubao
from .payment import paypal

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
        response_data = json.loads(response_json)
        # Task 3.5 Step 1: Set payment_no in the database with the payment ID generated from Paypal REST API
        payment.set_payment_no(response_data["id"])
        payment.save()
        return response
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

def generate_shipping_label(order):
    # Task 3.6 - TO DO: Generate shipping label


    shipping_label_url = f"/static/shipping_label/{order.token}.png"
    return shipping_label_url

# Task 3.6. - TO DO: PayPal refund
@login_required
def paypal_refund(order):
    return True

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

    # Task 3.6. - TO DO: Handle refund process for each payment method
    refund_success = True # Just example. Please update this based on the response
    if payment.payment_method == "paypal":
        refund_success = paypal_refund(order)
    else:
        pass # Can make a new function to handle other payment methods
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

    shipping_label_url = generate_shipping_label(order)

    # Task 3.6. - Create a new row for OrderReturn
    returnOrder = OrderReturn.query.filter_by(order_id=order.id).first()
    if not returnOrder:
        returnOrder = OrderReturn.create(
            order_id=order.id,
            status=OrderReturnStatusKinds.label_created.value,
            shipping_label=shipping_label_url,
            cancellation_time=datetime.now(timezone.utc),
            carrier=random.choice(["UPC", "DHL"])
        )

    return jsonify({
        "success": True,
        "shipping_label_url": shipping_label_url,
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
    
    flash(lazy_gettext("Your return will be picked up soon. Do not lose the shipping label and please attach it to your package"), "success")

    order.update(
        status=OrderStatusKinds.returned.value
    )

    return jsonify({
        "success": True,
        "message": "The status is already updated"
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
    app.register_blueprint(bp, url_prefix="/orders")
