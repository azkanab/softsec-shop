import os
import logging
import requests
import base64
import json

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
def capture_order(payment_id):
    client = get_paypal_client()
    orders_controller = client.orders

    order = orders_controller.capture_order(
        {"id": payment_id, "prefer": "return=representation"}
    )
    return Response(
        ApiHelper.json_serialize(order.body), status=200, mimetype="application/json"
    )


#Task 3.6

def get_access_token_manual():
    """
    Helper function to get a PayPal Access Token manually.
    Think of this as logging into PayPal to get a temporary pass-card.
    """
    client_id = current_app.config.get("PAYPAL_CLIENT_ID")
    client_secret = current_app.config.get("PAYPAL_CLIENT_SECRET")
    
    # URL for Sandbox (Test Mode). Change to live URL for real money.
    url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    
    # We scramble our ID and Secret into a special code (Base64) to log in safely.
    auth_str = f"{client_id}:{client_secret}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {"grant_type": "client_credentials"}
    
    # Send the login request
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"Login failed: {e}")
    
    return None

def refund_order(order_id, amount):
    """
    This function does two things:
    1. Looks inside the 'Order' folder to find the 'Capture ID' (The Receipt Number).
    2. Tells PayPal to refund that specific Receipt Number.
    """
    # 1. Login to get the access token
    access_token = get_access_token_manual()
    if not access_token:
        return Response(json.dumps({"error": "Could not log into PayPal"}), status=401)

    base_url = "https://api-m.sandbox.paypal.com"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 2. Look up the Order details
    # We need to find the 'Capture ID'. You can't refund an 'Order ID' directly.
    get_order_url = f"{base_url}/v2/checkout/orders/{order_id}"
    order_res = requests.get(get_order_url, headers=headers)
    
    if order_res.status_code != 200:
        return Response(json.dumps({"error": "Order not found"}), status=404)
    
    order_data = order_res.json()
    
    # Dig through the data to find the Capture ID
    try:
        # Path: purchase_units -> payments -> captures -> id
        capture_id = order_data['purchase_units'][0]['payments']['captures'][0]['id']
    except (KeyError, IndexError):
        return Response(json.dumps({"error": "No captured payment found to refund"}), status=400)

    # 3. Send the Refund Request
    refund_url = f"{base_url}/v2/payments/captures/{capture_id}/refund"
    
    payload = {
        "amount": {
            "value": str(amount),
            "currency_code": "USD" # Ensure this matches your store currency
        },
        "note_to_payer": "Refund for order cancellation"
    }
    
    refund_res = requests.post(refund_url, headers=headers, json=payload)

    # Return the result so the Manager (views.py) knows what happened
    return Response(
        refund_res.text, 
        status=refund_res.status_code, 
        mimetype="application/json"
    )