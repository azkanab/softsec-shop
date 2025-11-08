# -*- coding: utf-8 -*-
"""User views."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import lazy_gettext
from flask_login import current_user, login_required, login_user, logout_user
from pluggy import HookimplMarker

from flaskshop.order.models import Order
from flaskshop.utils import flash_errors
from flaskshop.extensions import csrf_protect as profile
from flaskshop.constant import Permission

from .forms import AddressForm, ChangePasswordForm, LoginForm, RegisterForm, ResetPasswd
from .models import User, UserAddress
from .utils import gen_tmp_pwd, send_reset_pwd_email

impl = HookimplMarker("flaskshop")


def index():
    form = ChangePasswordForm(request.form)
    orders = Order.get_current_user_orders()
    return render_template("account/details.html", form=form, orders=orders)


def login():
    """login page."""
    form = LoginForm(request.form)
    if form.validate_on_submit():
        login_user(form.user)
        redirect_url = request.args.get("next") or url_for("public.home")
        flash(lazy_gettext("You are log in."), "success")
        return redirect(redirect_url)
    else:
        flash_errors(form)
    return render_template("account/login.html", form=form)


def resetpwd():
    """Reset user password"""
    form = ResetPasswd(request.form)

    if form.validate_on_submit():
        flash(lazy_gettext("Check your e-mail."), "success")
        new_passwd = gen_tmp_pwd()
        send_reset_pwd_email(form.username.data, new_passwd)
        form.user.update(password=new_passwd)
        return redirect(url_for("account.login"))
    else:
        flash_errors(form)
    return render_template("account/login.html", form=form, reset=True)


@login_required
def logout():
    """Logout."""
    logout_user()
    flash(lazy_gettext("You are logged out."), "info")
    return redirect(url_for("public.home"))


def signup():
    """Register new user."""
    form = RegisterForm(request.form)
    if form.validate_on_submit():
        user = User.create(
            username=form.username.data,
            email=form.email.data.lower(),
            password=form.password.data,
            is_active=True,
        )
        login_user(user)
        flash(lazy_gettext("You are signed up."), "success")
        return redirect(url_for("public.home"))
    else:
        flash_errors(form)
    return render_template("account/signup.html", form=form)


def set_password():
    form = ChangePasswordForm(request.form)
    if form.validate_on_submit():
        current_user.update(password=form.password.data)
        flash(lazy_gettext("You have changed password."), "success")
    else:
        flash_errors(form)
    return redirect(url_for("account.index"))

# task 2.4.a vulnerable
# def view_profile(user_id):
#     user = User.get_by_id(user_id)
#     if not user:
#         flash("User not found", "error")
#         return redirect(url_for("public.home"))
    
#     return render_template('account/profile.html', 
#                          user=user,
#                          title=f"{user.username}'s Profile")

# task 2.4.a fix
def view_profile(user_id):
    user = User.get_by_id(user_id)
    # Add the Access Control Check (The Mitigation)
    # Check if the requested ID matches the current user's ID
    # OR if the current user has the ADMINISTER permission.
    if user_id != current_user.id and not current_user.can(Permission.ADMINISTER):
        # If neither is true, deny access (send 403 Forbidden)
        flash("not authorized", "error")
        return redirect(url_for("public.home"))
    if not user:
        flash("User not found", "error")
        return redirect(url_for("public.home"))
    
    return render_template('account/profile.html', 
                         user=user,
                         title=f"{user.username}'s Profile")

def addresses():
    """List addresses."""
    addresses = current_user.addresses
    return render_template("account/addresses.html", addresses=addresses)

# Task 2.1. CSRF - Removing the @profile.exempt
def edit_address():
    """Create and edit an address."""
    form = AddressForm(request.form)
    address_id = request.args.get("id", None, type=int)
    if address_id:
        user_address = UserAddress.get_by_id(address_id)
        form = AddressForm(request.form, obj=user_address)
    if request.method == "POST" and form.validate_on_submit():
        address_data = {
            "province": form.province.data,
            "city": form.city.data,
            "district": form.district.data,
            "address": form.address.data,
            "contact_name": form.contact_name.data,
            "contact_phone": form.contact_phone.data,
            "user_id": current_user.id,
        }
        if address_id:
            UserAddress.update(user_address, **address_data)
            flash(lazy_gettext("Success edit address."), "success")
        else:
            UserAddress.create(**address_data)
            flash(lazy_gettext("Success add address."), "success")
        return redirect(url_for("account.index") + "#addresses")
    else:
        flash_errors(form)
    return render_template(
        "account/address_edit.html", form=form, address_id=address_id
    )

def delete_address(id):
    user_address = UserAddress.get_by_id(id)
    if user_address in current_user.addresses:
        UserAddress.delete(user_address)
    return redirect(url_for("account.index") + "#addresses")

@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("account", __name__)
    bp.add_url_rule("/", view_func=index)
    bp.add_url_rule("/login", view_func=login, methods=["GET", "POST"])
    bp.add_url_rule("/resetpwd", view_func=resetpwd, methods=["GET", "POST"])
    bp.add_url_rule("/logout", view_func=logout)
    bp.add_url_rule("/signup", view_func=signup, methods=["GET", "POST"])
    bp.add_url_rule("/setpwd", view_func=set_password, methods=["POST"])
    bp.add_url_rule("/address", view_func=addresses)
    bp.add_url_rule("/address/edit", view_func=edit_address, methods=["GET", "POST"])
    bp.add_url_rule(
        "/address/<int:id>/delete", view_func=delete_address, methods=["POST"]
    )
    bp.add_url_rule('/profile/<int:user_id>', view_func=view_profile)
    app.register_blueprint(bp, url_prefix="/account")
