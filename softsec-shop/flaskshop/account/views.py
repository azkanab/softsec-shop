# -*- coding: utf-8 -*-
"""User views."""
from flask import Blueprint, flash, redirect, render_template, request, url_for, session
from flask_babel import lazy_gettext
from flask_login import current_user, login_required, login_user, logout_user
from pluggy import HookimplMarker

from flaskshop.order.models import Order
from flaskshop.utils import flash_errors
from flaskshop.extensions import csrf_protect as profile
from flaskshop.constant import Permission

from .forms import AddressForm, ChangePasswordForm, LoginForm, RegisterForm, ResetPasswd, Verify2FAForm, ForceResetPasswdForm
from .models import User, UserAddress
from .utils import gen_tmp_pwd, send_reset_pwd_email

import pyotp
import qrcode
from io import BytesIO
import base64

impl = HookimplMarker("flaskshop")


def index():
    form = ChangePasswordForm(request.form)
    orders = Order.get_current_user_orders()

    # task 3.3. Initialize the QR code data for the tab pane
    qr_code_base64 = None
    secret = session.get('otp_secret')
    
    # If the user is currently logged in but hasn't started enrollment, start it now
    if current_user.is_authenticated and 'otp_secret' not in session:
        session['otp_secret'] = pyotp.random_base32()
        secret = session['otp_secret']
        
    if secret:
        # Generate QR code data (as done in the original enable_2fa function)
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=current_user.email,
            issuer_name='FlaskShop' 
        )
        img = qrcode.make(uri)
        buf = BytesIO()
        img.save(buf)
        qr_code_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    # The form used inside the 2FA tab will be the Verify2FAForm
    verify_form = Verify2FAForm()
    
    # --- END task 3.3 frontend ---
    
    return render_template("account/details.html", 
                           form=form, # ChangePasswordForm
                           verify_form=verify_form, # New Verify2FAForm
                           qr_code=qr_code_base64, # QR code data
                           orders=orders)
    # return render_template("account/details.html", form=form, orders=orders)


def login():
    """login page."""
    form = LoginForm(request.form)
    if form.validate_on_submit():
        # --- PRODUCTION READY 2FA CHECK ---
        
        # 1. Look for the unique permanent session flag for this user ID.
        #    If it's present, 2FA is required.
        is_2fa_required = session.get(f'2fa_enabled_{form.user.id}')
        
        if is_2fa_required: 
            
            # 2. Block standard login and set a flag to identify the user for the 2FA step.
            session['awaiting_2fa_user_id'] = form.user.id
            flash(lazy_gettext("Two-Factor Authentication required."), "info")
            
            # 3. Redirect to the 2FA page
            return redirect(url_for("account.verify_2fa")) 
        
        # --- END PRODUCTION READY 2FA CHECK ---
        login_user(form.user)
        if form.user.is_suspicious:
            redirect_url = url_for("account.forceresetpwd")
            flash(lazy_gettext("Your password is breached. Please change your password"), "warning")
        else:
            redirect_url = request.args.get("next") or url_for("public.home")
            flash(lazy_gettext("You are log in."), "success")
        return redirect(redirect_url)
    else:
        flash_errors(form)
    return render_template("account/login.html", form=form)

# Task 3.2 - API for force reset password
def forceresetpwd():
    """Force Reset user password"""
    form = ForceResetPasswdForm(request.form)

    if form.validate_on_submit():
        user = User.get_by_id(current_user.id)
        user.update(
            password=form.new_password.data,
            is_suspicious=False
        )
        user.save()
        flash(lazy_gettext("Your password has been successfully updated. Please log in with your new password."), "success")
        logout_user()
        return redirect(url_for("account.login"))
    else:
        flash_errors(form)
    return render_template("account/login.html", form=form, force_reset=True)

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

# # task3.3 draft
@login_required
def enable_2fa():
    # Check if a secret already exists in the session (if they refresh the page)
    if 'otp_secret' not in session:
        # Generate a new 16-character unique secret key
        session['otp_secret'] = pyotp.random_base32()

    secret = session['otp_secret']

    # Create the special URI (a string the Authenticator app can read)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name='FlaskShop' 
    )

    # Instantiate the form to get the CSRF token.
    form = Verify2FAForm()

    # Generate the QR Code Image and encode it for the browser
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf)
    # Encode the image data into a string so it can be passed to the HTML template
    qr_code_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template("account/enable_2fa.html", qr_code=qr_code_base64, form=form)


def verify_2fa():
    # 1. Determine which user we are validating:
    
    # A. User is fully logged in and is in the process of initial ENROLLMENT
    if current_user.is_authenticated:
        user = current_user
        # The secret for enrollment is stored temporarily in 'otp_secret'
        secret_key = session.get('otp_secret')
        # Target action after success: Redirect to account index
        success_redirect_url = url_for('account.index')
        
    # B. User is NOT logged in but has passed password check (FINAL LOGIN)
    else:
        user_id_awaiting_2fa = session.get('awaiting_2fa_user_id')
        if not user_id_awaiting_2fa:
            # They didn't come from the login page—send them there.
            flash(lazy_gettext("Please log in first."), "warning")
            return redirect(url_for('account.login'))
            
        user = User.get_by_id(user_id_awaiting_2fa)
        
        # The secret for final login is the *permanent* flag you set earlier
        secret_key = session.get(f'2fa_enabled_{user.id}')
        
        # Target action after success: Log the user in
        success_redirect_url = url_for('public.home')


    # 2. Handle missing secret/user error (The original error point)
    if not user or not secret_key:
        flash("2FA setup error. Please restart enrollment.", "error")
        # Since we don't know the state, send them to the safe login page
        return redirect(url_for('account.login')) 
        
    # 3. Validation and Form Submission
    form = Verify2FAForm(request.form) 
    
    if request.method == "POST" and form.validate_on_submit():
        totp = pyotp.TOTP(secret_key)
        entered_code = form.otp_code.data

        if totp.verify(entered_code):
            
            # Successful validation: Now finalize the session based on the state
            if current_user.is_authenticated:
                # ENROLLMENT: Set the permanent flag to the actual secret string

                # Retrieve the temporary secret we need to save permanently
                secret_to_save = session.get('otp_secret')

                session.permanent = True
                # Store the actual secret string under the permanent key!
                session[f'2fa_enabled_{user.id}'] = secret_to_save

                # Task 3.3 Update the database to save 2FA status
                user.update(
                    is_2fa_enabled=True
                )

                # Clean up temporary secret
                del session['otp_secret']
                flash("2FA successfully enabled!", "success")
            
            else:
                # FINAL LOGIN: Log the user in and clean up login flag
                login_user(user) 
                del session['awaiting_2fa_user_id']
                flash(lazy_gettext("Login successful."), "success")

            return redirect(success_redirect_url)

        else:
            flash("Invalid TOTP code. Please try again.", "error")
    
    return render_template("account/verify_2fa.html", form=form)

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

# Task 3.2 - If a logged in account is flagged for being suspicious (is_suspicious = True), it must be redirected to forceresetpwd page
def check_suspicious_user():
    allowed_endpoints = ['account.forceresetpwd', 'account.logout', 'static']

    if current_user.is_authenticated: # if user is logged in
        if current_user.is_suspicious:
            if request.endpoint not in allowed_endpoints:
                flash(lazy_gettext("Your password is breached. Please change your password"), "warning")
                return redirect(url_for("account.forceresetpwd"))

@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("account", __name__)
    bp.add_url_rule("/", view_func=index)
    bp.add_url_rule("/login", view_func=login, methods=["GET", "POST"])
    bp.add_url_rule("/resetpwd", view_func=resetpwd, methods=["GET", "POST"])
    # Task 3.2 - New endpoint for force reset when user is suspicious
    bp.add_url_rule("/forceresetpwd", view_func=forceresetpwd, methods=["GET", "POST"])
    bp.add_url_rule("/logout", view_func=logout)
    bp.add_url_rule("/signup", view_func=signup, methods=["GET", "POST"])
    bp.add_url_rule("/setpwd", view_func=set_password, methods=["POST"])
    bp.add_url_rule("/address", view_func=addresses)
    bp.add_url_rule("/address/edit", view_func=edit_address, methods=["GET", "POST"])
    bp.add_url_rule("/verify_2fa", view_func=verify_2fa, methods=["GET", "POST"]) 
    bp.add_url_rule(
        "/address/<int:id>/delete", view_func=delete_address, methods=["POST"]
    )
    bp.add_url_rule('/profile/<int:user_id>', view_func=view_profile)

    # Task 3.2 - Check if the user is suspicious before going to every page, if it is, then it will be redirected to reset password
    app.before_request(check_suspicious_user)

    app.register_blueprint(bp, url_prefix="/account")
