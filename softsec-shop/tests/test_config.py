# -*- coding: utf-8 -*-
"""Test configs."""
from flaskshop.app import create_app
from flaskshop.settings import Config, ProdConfig


def test_production_config():
    """Production config."""
    app = create_app(ProdConfig)
    assert app.config["ENV"] == "prod"  # nosec B101
    assert app.config["FLASK_DEBUG"] is False  # nosec B101
    assert app.config["DEBUG_TB_ENABLED"] is False  # nosec B101


def test_dev_config():
    """Development config."""
    app = create_app(Config)
    assert app.config["ENV"] == "dev"  # nosec B101
    # assert app.config["FLASK_DEBUG"] is True
