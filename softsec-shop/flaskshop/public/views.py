# -*- coding: utf-8 -*-
"""Public section, including homepage and signup."""
from flask import Blueprint, current_app, render_template, request, send_from_directory
from pluggy import HookimplMarker

from flaskshop.account.models import User
from flaskshop.extensions import login_manager, db
from flaskshop.product.models import Product

from .models import Page
from .search import Item

impl = HookimplMarker("flaskshop")


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.get_by_id(int(user_id))


def home():
    products = Product.get_featured_product()
    return render_template("public/home.html", products=products)


def style():
    return render_template("public/style_guide.html")


def favicon():
    return send_from_directory("static", "favicon-32x32.png")

def search():
    print("invoke search()")
    query = request.args.get("q", "")
    page = request.args.get("page", default=1, type=int)
    per_page = 10
    
    if current_app.config["USE_ES"]:
        pagination = Item.new_search(query, page)
    else:
        from sqlalchemy import text

        total = 100 # TODO: Fix this static value with dynamic value
        # Get paginated results with product images
        offset = (page - 1) * per_page
        sql = text(f"""
            SELECT p.*, 
                   (SELECT image FROM product_image WHERE product_id = p.id LIMIT 1) as first_image
            FROM product_product p
            WHERE p.title LIKE '%%{query}%%'
            ORDER BY p.id
            LIMIT {per_page} OFFSET {offset}
        """)
        offset = db.session.execute(sql)
        
        # Convert to proper product objects with required properties
        pagei = []
        for row in offset.mappings():
            it = dict(row)
            # Add properties that the template expects
            it['first_img'] = f"/static/{it.pop('first_image', '')}" if it.get('first_image') else ''
            it['price'] = f"{it.get('basic_price', 0):.2f}"
            it['is_discounted'] = False  # TODO: Implement discount logic
            pagei.append(it)
        
        # Create a pagination-like object
        class Pagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                
            def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if (num <= left_edge or 
                        (self.page - left_current - 1 < num < self.page + right_current) or 
                        num > self.pages - right_edge):
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num
        
        pagination = Pagination(pagei, page, per_page, total)
    
    return render_template(
        "public/search_result.html",
        products=pagination.items,
        query=query,
        pagination=pagination,
    )

def show_page(identity):
    page = Page.get_by_identity(identity)
    return render_template("public/page.html", page=page)


@impl
def flaskshop_load_blueprints(app):
    bp = Blueprint("public", __name__)
    bp.add_url_rule("/", view_func=home)
    bp.add_url_rule("/style", view_func=style)
    bp.add_url_rule("/favicon.ico", view_func=favicon)
    bp.add_url_rule("/search", view_func=search)
    bp.add_url_rule("/page/<identity>", view_func=show_page)
    app.register_blueprint(bp)
