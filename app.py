from flask import Flask, render_template, request, redirect, url_for, session, flash
import database as db
from utils import fmt_price, fmt_status

app = Flask(__name__)
app.secret_key = "auctionhumg_secret_2024"

db.create_tables()
db.seed_data()


def login_required(role=None):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Vui lòng đăng nhập.", "warning")
                return redirect(url_for("login"))
            if role and session.get("user_role") != role:
                flash("Bạn không có quyền truy cập trang này.", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_helpers():
    return dict(fmt_price=fmt_price, fmt_status=fmt_status)


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get("user_role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "seller":
        return redirect(url_for("seller_create"))
    return redirect(url_for("bidder_auctions"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.login(username, password)
        if user:
            session["user_id"]       = user["id"]
            session["user_username"] = user["username"]
            session["user_role"]     = user["role"]
            session["user_fullname"] = user["full_name"] or user["username"]
            return redirect(url_for("index"))
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        email    = request.form.get("email", "").strip()
        fullname = request.form.get("full_name", "").strip()
        role     = request.form.get("role", "buyer")

        if len(password) < 6:
            flash("Mật khẩu phải có ít nhất 6 ký tự.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Mật khẩu nhập lại không khớp.", "danger")
            return render_template("register.html")
        ok, msg = db.register(username, password, email, fullname, role)
        if ok:
            flash(f"Tài khoản '{username}' đã được tạo! Vui lòng đăng nhập.", "success")
            return redirect(url_for("login"))
        flash(msg, "danger")
    return render_template("register.html")


@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    pending = db.get_products(status="pending")
    return render_template("admin/dashboard.html", products=pending)


@app.route("/admin/approve/<int:pid>")
@login_required(role="admin")
def admin_approve(pid):
    db.update_product_status(pid, "active")
    flash("✓ Sản phẩm đã được duyệt.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reject/<int:pid>")
@login_required(role="admin")
def admin_reject(pid):
    db.update_product_status(pid, "rejected")
    flash("✗ Sản phẩm đã bị từ chối.", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/categories", methods=["GET", "POST"])
@login_required(role="admin")
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        ok, msg = db.add_category(name, desc)
        if ok:
            flash("Đã thêm danh mục.", "success")
        else:
            flash(msg, "danger")
    cats = db.get_categories()
    return render_template("admin/categories.html", categories=cats)


@app.route("/admin/categories/delete/<int:cid>")
@login_required(role="admin")
def admin_delete_category(cid):
    ok, msg = db.delete_category(cid)
    if ok:
        flash("Đã xóa danh mục.", "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("admin_categories"))


@app.route("/admin/users")
@login_required(role="admin")
def admin_users():
    users = db.get_all_users()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/role/<int:uid>/<new_role>")
@login_required(role="admin")
def admin_change_role(uid, new_role):
    if uid != session["user_id"]:
        db.update_user_role(uid, new_role)
        flash("Đã cập nhật quyền.", "success")
    return redirect(url_for("admin_users"))


@app.route("/seller/create", methods=["GET", "POST"])
@login_required(role="seller")
def seller_create():
    cats = db.get_category_names()
    if request.method == "POST":
        title     = request.form.get("title", "").strip()
        desc      = request.form.get("description", "").strip()
        category  = request.form.get("category", "")
        start_t   = request.form.get("start_time", "").strip()
        end_t     = request.form.get("end_time", "").strip()
        try:
            start_price = int(request.form.get("start_price", "0").replace(",", ""))
            step_price  = int(request.form.get("step_price",  "0").replace(",", ""))
            bn_str      = request.form.get("buy_now_price", "").strip()
            buy_now     = int(bn_str.replace(",", "")) if bn_str else None
        except ValueError:
            flash("Giá phải là số nguyên hợp lệ.", "danger")
            return render_template("seller/create.html", categories=cats)

        ok, msg = db.create_product(
            session["user_id"], category, title, desc, None,
            start_price, step_price, buy_now, start_t, end_t)
        if ok:
            flash(f"'{title}' đã gửi. Chờ Admin duyệt.", "success")
            return redirect(url_for("seller_manage"))
        flash(msg, "danger")
    return render_template("seller/create.html", categories=cats)


@app.route("/seller/manage")
@login_required(role="seller")
def seller_manage():
    products = db.get_products(seller_id=session["user_id"])
    bids_map = {p["id"]: db.get_bids_for_product(p["id"]) for p in products}
    return render_template("seller/manage.html", products=products, bids_map=bids_map)


@app.route("/bidder/auctions")
@login_required(role="buyer")
def bidder_auctions():
    products = db.get_products(status="active")
    bids_map = {p["id"]: db.get_bids_for_product(p["id"]) for p in products}
    return render_template("bidder/auctions.html", products=products, bids_map=bids_map)


@app.route("/bidder/bid/<int:pid>", methods=["POST"])
@login_required(role="buyer")
def bidder_place_bid(pid):
    try:
        amount = int(request.form.get("amount", "0").replace(",", ""))
    except ValueError:
        flash("Giá đặt không hợp lệ.", "danger")
        return redirect(url_for("bidder_auctions"))
    ok, msg = db.place_bid(pid, session["user_id"], amount)
    if ok:
        flash(f"Đặt giá {fmt_price(amount)} thành công!", "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("bidder_auctions"))


@app.route("/bidder/mybids")
@login_required(role="buyer")
def bidder_my_bids():
    records = db.get_bids_by_user(session["user_id"])
    return render_template("bidder/my_bids.html", records=records)


if __name__ == "__main__":
    app.run(debug=True)
