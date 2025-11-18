import time
import json
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    url_for,
    jsonify
)

from flask_babel import lazy_gettext
from flask_login import current_user, login_required
from pluggy import HookimplMarker

from flaskshop.constant import OrderStatusKinds, PaymentStatusKinds, ShipStatusKinds
from flaskshop.extensions import csrf_protect
from .payment import zhifubao
from .payment import paypal

from .models import Order, OrderPayment

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
def cancel_order(token):
    order = Order.query.filter_by(token=token).first()
    if not order.is_self_order:
        abort(403, "This is not your order!")
    order.cancel()
    return render_template("orders/details.html", order=order)


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
    bp.add_url_rule("/cancel/<string:token>", view_func=cancel_order)
    bp.add_url_rule("/receive/<string:token>", view_func=receive)
    app.register_blueprint(bp, url_prefix="/orders")
