# -*- coding: utf-8 -*-
"""User forms."""
from flask_babel import lazy_gettext
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp
from flaskshop.account.utils import isPasswordBreached

from .models import User

class RegisterForm(FlaskForm):
    """Register form."""

    username = StringField(
        lazy_gettext("Username"),
        validators=[
            DataRequired(),
            Length(min=3, max=25),
            Regexp(
                "^[a-zA-Z0-9]*$",
                message=lazy_gettext(
                    "The username should contain only a-z, A-Z and 0-9."
                ),
            ),
        ],
    )
    email = StringField(
        lazy_gettext("Email"),
        validators=[DataRequired(), Email(), Length(min=6, max=40)],
    )
    # Task 3.2 - Add minimum length for password when registering account
    password = PasswordField(
        lazy_gettext("Password"), validators=[DataRequired(), Length(min=15, max=64)]
    )
    confirm = PasswordField(
        lazy_gettext("Verify password"),
        [
            DataRequired(),
            EqualTo("password", message=lazy_gettext("Passwords must match")),
        ],
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self, extra_validators=None):
        """Validate the form."""
        initial_validation = super(RegisterForm, self).validate(extra_validators)
        if not initial_validation:
            return False
        user = User.query.filter_by(username=self.username.data).first()
        if user:
            self.username.errors.append(lazy_gettext("Username already registered"))
            return False
        user = User.query.filter_by(email=self.email.data).first()
        if user:
            self.email.errors.append(lazy_gettext("Email already registered"))
            return False
        # Task 3.2 - Check using pwned API if the input password has already been breached
        if isPasswordBreached(self.password.data):
            self.password.errors.append(lazy_gettext("This password is already breached. Please choose another password!"))
            return False
        return True
        
class ResetPasswd(FlaskForm):
    """Password reset"""

    username = StringField(lazy_gettext("Email"), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(ResetPasswd, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self, extra_validators=None):
        """Validate the form."""
        initial_validation = super(ResetPasswd, self).validate(extra_validators)
        if not initial_validation:
            return False

        if "@" not in self.username.data:
            self.username.errors.append(lazy_gettext("Invalid"))
            return False

        self.user = User.query.filter_by(email=self.username.data).first()
        if not self.user:
            self.username.errors.append(lazy_gettext("Unknown username"))
            return False
        if not self.user.is_active:
            self.username.errors.append(lazy_gettext("User not activated"))
            return False

        return True
    
# Task 3.2 - Form for force resetting password when there is data breach or the account is flagged for suspicious activity
class ForceResetPasswdForm(FlaskForm):
    """Force Password Reset (if the account is suspected)"""

    new_password = PasswordField(lazy_gettext("New Password"), validators=[DataRequired(), Length(max=64)])
    confirm_password = PasswordField(lazy_gettext("Confirm New Password"), validators=[DataRequired(), EqualTo("new_password", message=lazy_gettext("Passwords must match")),])

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(ForceResetPasswdForm, self).__init__(*args, **kwargs)
        self.user = current_user

    def validate(self, extra_validators=None):
        """Validate the form."""
        initial_validation = super(ForceResetPasswdForm, self).validate(extra_validators)
        if not initial_validation:
            return False

        # Task 3.2. Check minimum password length based on 2FA status
        min_length = 8 if self.user.is_2fa_enabled else 15
        if len(self.new_password.data) < min_length:
            self.new_password.errors.append(lazy_gettext(f"Password must be at least {min_length} characters long."))
            return False

        if self.user.check_password(self.new_password.data):
            self.new_password.errors.append(lazy_gettext("New password cannot be the same as old password. Please choose another password!"))
            return False

        if isPasswordBreached(self.new_password.data):
            self.new_password.errors.append(lazy_gettext("This password is already breached. Please choose another password!"))
            return False

        return True


class LoginForm(FlaskForm):
    """Login form."""

    username = StringField(
        lazy_gettext("Username Or Email"), validators=[DataRequired()]
    )
    password = PasswordField(lazy_gettext("Password"), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(LoginForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self, extra_validators=None):
        """Validate the form."""
        initial_validation = super(LoginForm, self).validate(extra_validators)
        if not initial_validation:
            return False

        if "@" in self.username.data:
            self.user = User.query.filter_by(email=self.username.data).first()
        else:
            self.user = User.query.filter_by(username=self.username.data).first()
        if not self.user:
            self.username.errors.append(lazy_gettext("Unknown username"))
            return False

        if not self.user.check_password(self.password.data):
            self.password.errors.append(lazy_gettext("Invalid password"))
            return False

        if not self.user.is_active:
            self.username.errors.append(lazy_gettext("User not activated"))
            return False
        return True


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField(
        lazy_gettext("Old Password"), validators=[DataRequired()]
    )
    # Task 3.2 Add minimum length for password when changing password
    password = PasswordField(lazy_gettext("Password"), validators=[DataRequired(), Length(max=64)])
    confirm = PasswordField(
        lazy_gettext("Verify password"),
        validators=[
            DataRequired(),
            EqualTo("password", message=lazy_gettext("Passwords must match")),
        ],
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super().__init__(*args, **kwargs)
        self.user = current_user

    def validate(self, extra_validators=None):
        """Validate the form."""
        initial_validation = super().validate(extra_validators)
        if not initial_validation:
            return False

        # Task 3.2. Check minimum password length based on 2FA status
        min_length = 8 if self.user.is_2fa_enabled else 15
        if len(self.password.data) < min_length:
            self.password.errors.append(lazy_gettext(f"Password must be at least {min_length} characters long."))
            return False

        if not self.user.check_password(self.old_password.data):
            self.old_password.errors.append(lazy_gettext("Invalid password"))
            return False

        # Task 3.2 - Check using pwned API if the input password has already been breached
        if isPasswordBreached(self.password.data):
            self.password.errors.append(lazy_gettext("This password is already breached. Please choose another password!"))
            return False

        return True


class AddressForm(FlaskForm):
    """Address form."""

    province = StringField(lazy_gettext("Province"), validators=[DataRequired()])
    city = StringField(lazy_gettext("City"), validators=[DataRequired()])
    district = StringField(lazy_gettext("District"), validators=[DataRequired()])
    address = StringField(lazy_gettext("Address"), validators=[DataRequired()])
    contact_name = StringField(
        lazy_gettext("Contact name"), validators=[DataRequired()]
    )
    contact_phone = StringField(
        lazy_gettext("Contact Phone"),
        validators=[DataRequired(), Length(min=10, max=13)],
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        kwargs['meta'] = {'csrf': False}
        super().__init__(*args, **kwargs)

# 3.3 new class
class Verify2FAForm(FlaskForm):
    """Form to verify the 6-digit TOTP code."""
    otp_code = StringField(
        lazy_gettext("Six-Digit Code"),
        [
            DataRequired(), 
            Length(min=6, max=6)
        ],
        description=lazy_gettext('Enter the code from your authenticator app.')
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super().__init__(*args, **kwargs) 