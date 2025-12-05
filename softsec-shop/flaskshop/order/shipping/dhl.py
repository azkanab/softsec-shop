import requests
import json
from flaskshop.utils import detect_postal_and_country

from flask import current_app

# Task 3.6. Requesting Return Shipping Label to DHL Service
def get_dhl_return_shipping_label(order):
    DHL_API_KEY = current_app.config.get("DHL_API_KEY")
    DHL_API_URL = current_app.config.get("DHL_API_URL")
    DHL_USERNAME = current_app.config.get("DHL_USERNAME")
    DHL_PASSWORD = current_app.config.get("DHL_PASSWORD")
    
    address = order.shipping_address

    # Task 3.6.: Build payload request
    if not address: # Fallback address
        shipper = {
            "name1": "Technische Universität Hamburg",
            "addressStreet": "Am Schwarzenberg-Campus",
            "addressHouse": "1",
            "postalCode": "21073",
            "city": "Hamburg",
            "country": "DE",
            "phone": "+4942359873804"
        }
    else:
        postal, country = detect_postal_and_country(address.address)
        shipper = {
            "name1": address.contact_name,
            "addressStreet": address.address,
            "addressHouse": "1",
            "postalCode": postal,
            "city": address.city,
            "country": country,
            "phone": address.contact_phone
        }

    payload = {
        "receiverId": "deu",
        "customerReference": str(order.id),
        "shipper": shipper,
        "itemWeight": {"uom": "g", "value": 1000},
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'dhl-api-key': DHL_API_KEY
    }
    
    payload_json = json.dumps(payload)

    # Task 3.6. Send request to DHL
    response = requests.post(
        DHL_API_URL,
        headers=headers,
        data=payload_json,
        auth=(DHL_USERNAME, DHL_PASSWORD),
    )
    response.raise_for_status()
    
    return response