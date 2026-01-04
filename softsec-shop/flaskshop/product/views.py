# -*- coding: utf-8 -*-
"""Product views."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user
from pluggy import HookimplMarker

from flaskshop.checkout.models import Cart
from flaskshop.order.models import Order
from flaskshop.constant import OrderStatusKinds
from flaskshop.database import db

from .forms import AddCartForm, ReviewForm
from .models import Category, Product, ProductCollection, ProductVariant, ProductReview

impl = HookimplMarker("flaskshop")


def show(id, form=None):
    product = Product.get_by_id(id)
    if not form:
        form = AddCartForm(request.form, product=product)
    return render_template("products/details.html", product=product, form=form)


@login_required
def product_add_to_cart(id):
    """this method return to the show method and use a form instance for display validater errors"""
    product = Product.get_by_id(id)
    form = AddCartForm(request.form, product=product)

    if form.validate_on_submit():
        Cart.add_to_currentuser_cart(form.quantity.data, form.variant.data)
    return redirect(url_for("product.show", id=id))


def variant_price(id):
    variant = ProductVariant.get_by_id(id)
    return jsonify({"price": float(variant.price), "stock": variant.stock})


def show_category(id):
    page = request.args.get("page", 1, type=int)
    ctx = Category.get_product_by_category(id, page)
    return render_template("category/index.html", **ctx)


def show_collection(id):
    page = request.args.get("page", 1, type=int)
    ctx = ProductCollection.get_product_by_collection(id, page)
    return render_template("category/index.html", **ctx)


@login_required
def show_review_form(product_id, order_token):
    """Display review form for a product from a completed order."""
    product = Product.get_by_id(product_id)
    if not product:
        abort(404, "Product not found")

    # Verify order belongs to current user and is completed
    order = Order.query.filter_by(token=order_token).first()
    if not order:
        abort(404, "Order not found")

    if order.user_id != current_user.id:
        abort(403, "You do not have permission to review this order")

    if order.status != OrderStatusKinds.completed.value:
        abort(403, "You can only review products from completed orders")

    # Check if user can review this product for this specific order
    can_review, message = ProductReview.can_user_review_product_in_order(
        current_user.id, product_id, order.id
    )
    if not can_review:
        flash(message, "warning")
        return redirect(url_for("product.show", id=product_id))

    form = ReviewForm()
    form.order_id.data = order.id

    return render_template("products/review_form.html", product=product, form=form, order=order)


@login_required
def submit_review(product_id):
    """Submit a product review with security validations."""
    product = Product.get_by_id(product_id)
    if not product:
        abort(404, "Product not found")

    form = ReviewForm()

    if form.validate_on_submit():
        order_id = form.order_id.data

        # Check if user can review this product for this specific order
        can_review, message = ProductReview.can_user_review_product_in_order(
            current_user.id, product_id, order_id
        )

        if not can_review:
            flash(message, "warning")
            return redirect(url_for("product.show", id=product_id))

        # Create review
        ProductReview.create(
            product_id=product_id,
            user_id=current_user.id,
            order_id=order_id,
            packaging_rate=form.packaging_rate.data,
            delivery_rate=form.delivery_rate.data,
            item_rate=form.item_rate.data
        )

        # Update product rating and review count
        ProductReview.update_product_rating(product_id)
        db.session.commit()

        flash("Thank you for your review!", "success")
        return redirect(url_for("product.show", id=product_id))

    # If form validation fails, redirect to product page
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{field}: {error}", "danger")

    # Redirect to product page instead (since we don't have order token in failed validation)
    return redirect(url_for("product.show", id=product_id))


def get_product_reviews(product_id):
    """Get reviews for a product (JSON endpoint)."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = ProductReview.get_reviews_by_product(product_id, page, per_page)

    reviews = []
    for review in pagination.items:
        reviews.append({
            "id": review.id,
            "author": review.author_display_name,
            "date": review.date_of_submission.strftime("%Y-%m-%d"),
            "packaging_rate": review.packaging_rate,
            "delivery_rate": review.delivery_rate,
            "item_rate": review.item_rate,
            "average_rating": review.average_rating
        })

    # Get product to return accurate rating
    product = Product.get_by_id(product_id)
    overall_rating = float(product.rating) if product else 0.0

    return jsonify({
        "reviews": reviews,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
        "overall_rating": overall_rating
    })


@login_required
def recalculate_product_rating(product_id):
    """Utility route to recalculate rating for a product. Useful for fixing existing data."""
    # Security: Only allow admin users to recalculate ratings
    # If you don't have an admin system, you can check for specific user IDs
    # or remove this route entirely after fixing existing data
    if not current_user.is_authenticated:
        abort(403, "Authentication required")

    product = Product.get_by_id(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    # Recalculate rating
    ProductReview.update_product_rating(product_id)
    db.session.commit()

    # Get updated product
    product = Product.get_by_id(product_id)

    return jsonify({
        "success": True,
        "product_id": product_id,
        "new_rating": float(product.rating),
        "review_count": product.review_count,
        "message": f"Rating recalculated successfully. New rating: {product.rating}/5.0 ({product.review_count} reviews)"
    })


@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("product", __name__)
    bp.add_url_rule("/<int:id>", view_func=show)
    bp.add_url_rule("/api/variant_price/<int:id>", view_func=variant_price)
    bp.add_url_rule("/<int:id>/add", view_func=product_add_to_cart, methods=["POST"])
    bp.add_url_rule("/category/<int:id>", view_func=show_category)
    bp.add_url_rule("/collection/<int:id>", view_func=show_collection)
    bp.add_url_rule("/<int:product_id>/review/<string:order_token>", view_func=show_review_form)
    bp.add_url_rule("/<int:product_id>/review/submit", view_func=submit_review, methods=["POST"])
    bp.add_url_rule("/api/reviews/<int:product_id>", view_func=get_product_reviews)
    bp.add_url_rule("/api/recalculate-rating/<int:product_id>", view_func=recalculate_product_rating)

    app.register_blueprint(bp, url_prefix="/products")
