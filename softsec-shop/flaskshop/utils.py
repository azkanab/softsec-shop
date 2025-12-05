# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""

import logging
import re
import random
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode

from flask import current_app, flash, request
from flask_sqlalchemy.record_queries import get_recorded_queries

from flaskshop.checkout.models import Cart
from flaskshop.constant import SiteDefaultSettings
from flaskshop.dashboard.models import Setting
from flaskshop.plugin.utils import template_hook
from flaskshop.public.models import MenuItem


def flash_errors(form, category="warning"):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text} - {error}", category)


def log_slow_queries(app):
    formatter = logging.Formatter(
        "[%(asctime)s]{%(pathname)s:%(lineno)d}\n%(levelname)s - %(message)s"
    )
    handler = RotatingFileHandler(
        "slow_queries.log", maxBytes=10_000_000, backupCount=10
    )
    handler.setLevel(logging.WARN)
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

    @app.after_request
    def after_request(response):
        for query in get_recorded_queries():
            if query.duration >= app.config["DATABASE_QUERY_TIMEOUT"]:
                app.logger.warn(
                    f"Context: {query.location}\n"
                    f"SLOW QUERY: {query.statement}\n"
                    f"Parameters: {query.parameters}\n"
                    f"Duration: {query.duration}"
                )
        return response


def jinja_global_varibles(app):
    """Register global varibles for jinja2"""

    @app.context_processor
    def inject_cart():
        current_user_cart = Cart.get_current_user_cart()
        return dict(current_user_cart=current_user_cart)

    @app.context_processor
    def inject_menus():
        top_menu = (
            MenuItem.query.filter(MenuItem.position == 1)
            .filter(MenuItem.parent_id == 0)
            .order_by(MenuItem.order)
            .all()
        )
        bottom_menu = (
            MenuItem.query.filter(MenuItem.position == 2)
            .filter(MenuItem.parent_id == 0)
            .order_by(MenuItem.order)
            .all()
        )
        return dict(top_menu=top_menu, bottom_menu=bottom_menu)

    @app.context_processor
    def inject_site_setting():
        settings = {}
        for key, value in SiteDefaultSettings.items():
            obj = Setting.query.filter_by(key=key).first()
            if not obj:
                obj = Setting.create(key=key, **value)
            settings[key] = obj
        return dict(settings=settings)

    def get_sort_by_url(field, descending=False):
        request_get = request.args.copy()
        if descending:
            request_get["sort_by"] = "-" + field
        else:
            request_get["sort_by"] = field
        return f"{request.path}?{urlencode(request_get)}"

    app.add_template_global(current_app, "current_app")
    app.add_template_global(get_sort_by_url, "get_sort_by_url")
    app.add_template_global(template_hook, "run_hook")

import re
import random

# A small set of *real* German postcodes
VALID_GERMAN_POSTCODES = [
    "10115", "10117", "10119", "10178", "10179",   # Berlin
    "20095", "20097", "20099",                    # Hamburg
    "50667", "50668", "50670",                    # Köln
    "80331", "80333", "80335", "80336",           # München
    "01067", "01069", "01127",                    # Dresden
]


def extract_postal_code(address: str) -> str | None:
    """Extracts a postal-code-like fragment from a free-form address string."""
    if not address:
        return None

    patterns = [
        r"\b\d{5}\b",                           # 5 digits (DE style)
        r"\b[A-Z]\d[A-Z] \d[A-Z]\d\b",          # Canada
        r"\b[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}\b", # UK
        r"\b\d{3}-\d{4}\b",                     # Japan
    ]

    for p in patterns:
        m = re.search(p, address, flags=re.I)
        if m:
            return m.group(0)

    return None


def is_german_postal(postal: str | None) -> bool:
    """Return True if the postal code looks like a German one (5 digits only)."""
    if not postal:
        return False
    return bool(re.fullmatch(r"\d{5}", postal.strip()))
    

def detect_postal_and_country(address: str):
    """
    DHL rule:
    - If postal code is German -> keep it.
    - If postal is missing or clearly non-German -> fallback to a real German postal.
    Always return (postal, 'DE').
    """
    postal = extract_postal_code(address)

    if is_german_postal(postal):
        return postal, "DE"

    fallback_postal = random.choice(VALID_GERMAN_POSTCODES)
    return fallback_postal, "DE"
