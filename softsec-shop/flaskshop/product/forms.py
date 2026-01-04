from flask_wtf import FlaskForm
from wtforms import IntegerField, RadioField, HiddenField
from wtforms.validators import DataRequired, NumberRange
from wtforms.widgets.core import Input


class NumberInput(Input):
    input_type = "number"


class MyIntegerField(IntegerField):
    widget = NumberInput()


class AddCartForm(FlaskForm):
    variant = RadioField("variant", validators=[DataRequired()], coerce=int)
    quantity = MyIntegerField(
        "quantity", validators=[DataRequired(), NumberRange()], default=1
    )

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        if product:
            self.variant.choices = [(vari.id, vari) for vari in product.variant]


class ReviewForm(FlaskForm):
    """Form for submitting product reviews with star ratings."""

    packaging_rate = MyIntegerField(
        "Packaging Rating",
        validators=[DataRequired(), NumberRange(min=1, max=5)],
        default=1
    )
    delivery_rate = MyIntegerField(
        "Delivery Rating",
        validators=[DataRequired(), NumberRange(min=1, max=5)],
        default=1
    )
    item_rate = MyIntegerField(
        "Item Rating",
        validators=[DataRequired(), NumberRange(min=1, max=5)],
        default=1
    )
    order_id = HiddenField("Order ID", validators=[DataRequired()])
