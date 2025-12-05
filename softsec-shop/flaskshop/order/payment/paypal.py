import os
import logging
import requests
import base64
import json

from flask import Response, current_app

from paypalserversdk.exceptions.error_exception import ErrorException
from paypalserversdk.exceptions.api_exception import ApiException
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.logging.configuration.api_logging_configuration import (
    LoggingConfiguration,
    RequestLoggingConfiguration,
    ResponseLoggingConfiguration,
)
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.controllers.orders_controller import OrdersController
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.api_helper import ApiHelper

paypal_client = None

# Task 3.5 - Create Paypal Client using our Paypal Client ID and Paypal Client Secret API
def get_paypal_client():
    global paypal_client
    if paypal_client is None:
        paypal_client = PaypalServersdkClient(
            client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
                o_auth_client_id=current_app.config.get("PAYPAL_CLIENT_ID"),
                o_auth_client_secret=current_app.config.get("PAYPAL_CLIENT_SECRET"),
            ),

            logging_configuration=LoggingConfiguration(
                log_level=logging.INFO,
                mask_sensitive_headers=False,
                request_logging_config=RequestLoggingConfiguration(
                    log_headers=True, log_body=True
                ),
                response_logging_config=ResponseLoggingConfiguration(
                    log_headers=True, log_body=True
                ),
            )
        )
    return paypal_client

"""
Create an order to start the transaction.

@see https://developer.paypal.com/docs/api/orders/v2/#orders_create
"""

# Task 3.5 Step 1 - Create order/payment in Paypal server by calling Paypal REST API
def create_order(total_amount):
    client = get_paypal_client()
    orders_controller = client.orders

    order = orders_controller.create_order(
        {
            "body": OrderRequest(
                intent=CheckoutPaymentIntent.CAPTURE,
                purchase_units=[
                    PurchaseUnitRequest(
                        AmountWithBreakdown(currency_code="USD", value=str(total_amount))
                    )
                ],
            ),
            "prefer": "return=representation",
        }
    )
    return Response(
        ApiHelper.json_serialize(order.body), status=200, mimetype="application/json"
    )


"""
 Capture payment for the created order to complete the transaction.

 @see https://developer.paypal.com/docs/api/orders/v2/#orders_capture
"""

# Task 3.5 Step 2 - Finalize or capture order/payment in Paypal server by calling Paypal REST API
def capture_order(payment_id):
    client = get_paypal_client()
    orders_controller = client.orders

    order = orders_controller.capture_order(
        {"id": payment_id, "prefer": "return=representation"}
    )
    return Response(
        ApiHelper.json_serialize(order.body), status=200, mimetype="application/json"
    )

# Task 3.6. Helper to get order
def get_order(payment_id):
    client = get_paypal_client()
    orders_controller = client.orders

    order = orders_controller.get_order(
        {"id": payment_id}
    )
    return Response(
        ApiHelper.json_serialize(order.body), status=200, mimetype="application/json"
    )

# Task 3.6. Helper to get capture_id
def get_capture_id(payment_id):
    try:
        response = get_order(payment_id)

        order_data = json.loads(response.get_data(as_text=True))

        capture_id = order_data['purchase_units'][0]['payments']['captures'][0]['id']

        return capture_id
    except (KeyError, IndexError):
        return -1

# Task 3.6. - Refund Order
def refund_order(order_id, amount):
    """
    This function does two things:
    1. Looks inside the 'Order' folder to find the 'Capture ID' (The Receipt Number).
    2. Tells PayPal to refund that specific Receipt Number.
    """
    capture_id = get_capture_id(order_id)
    if capture_id == -1:
        return Response(json.dumps({"error": "No captured payment found to refund"}), status=400)

    client = get_paypal_client()
    payments_controller = client.payments
    collect = {
        'capture_id': capture_id,
        'prefer': 'return=minimal'
    }

    try:
        result = payments_controller.refund_captured_payment(collect)
        if result.is_success():
            return Response(
                ApiHelper.json_serialize(result.body), status=200, mimetype="application/json"
            )
        elif result.is_error():
            return Response(
                ApiHelper.json_serialize(result.errors), status=500, mimetype="application/json"
            )

    except ErrorException as e: 
        return Response(
            ApiHelper.json_serialize(e), status=500, mimetype="application/json"
        )
    except ApiException as e: 
        return Response(
            ApiHelper.json_serialize(e), status=500, mimetype="application/json"
        )