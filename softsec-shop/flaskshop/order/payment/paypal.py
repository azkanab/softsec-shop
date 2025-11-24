import os
import logging

from flask import Response, current_app

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
def capture_order(order_id):
    client = get_paypal_client()
    orders_controller = client.orders

    order = orders_controller.capture_order(
        {"id": order_id, "prefer": "return=representation"}
    )
    return Response(
        ApiHelper.json_serialize(order.body), status=200, mimetype="application/json"
    )