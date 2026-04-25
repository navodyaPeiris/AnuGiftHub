from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import mysql, bcrypt, mail
from flask_mail import Message
import os
from werkzeug.utils import secure_filename
from functools import wraps
from flask import abort

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def send_order_email(user_email, user_name, order_id, status):
    status_messages = {
        'confirmed': 'Your order has been confirmed! 🎉',
        'preparing': 'Your order is being prepared! 📦',
        'handed_to_courier': 'Your order has been handed to the courier! 🚚',
        'out_for_delivery': 'Your order is out for delivery! 🛵',
        'delivered': 'Your order has been delivered! ✅',
        'cancelled': 'Your order has been cancelled.'
    }
    message = status_messages.get(status, 'Your order status has been updated.')
    msg = Message(
        subject=f'AnuGiftHub - Order #{order_id} Update',
        sender='thathsaraninavodya04@gmail.com',
        recipients=[user_email]
    )
    msg.body = f'''
Dear {user_name},

{message}

Order ID: #{order_id}
Status: {status.replace('_', ' ').title()}

Thank you for shopping with AnuGiftHub! 🎁

Best regards,
AnuGiftHub Team
    '''
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Email error: {e}")

main = Blueprint('main', __name__)

UPLOAD_FOLDER = 'app/static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── HOME ─────────────────────────────────────────────────

@main.route('/')
def index():
    return render_template('index.html')

# ─── PRODUCTS ─────────────────────────────────────────────

@main.route('/products')
def products():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    cur.close()
    return render_template('products.html', products=products)

@main.route('/product/<int:id>', methods=['GET', 'POST'])
def product_detail(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products WHERE id = %s", (id,))
    product = cur.fetchone()

    if request.method == 'POST' and current_user.is_authenticated:
        comment = request.form.get('comment')
        cur.execute("INSERT INTO comments (user_id, product_id, content) VALUES (%s, %s, %s)",
                    (current_user.id, id, comment))
        mysql.connection.commit()
        flash('Comment posted!', 'success')

    cur.execute("""
        SELECT comments.*, users.name as user_name
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.product_id = %s
        ORDER BY comments.created_at DESC
    """, (id,))
    comments = cur.fetchall()
    cur.close()
    return render_template('product_detail.html', product=product, comments=comments)

# ─── AUTH ─────────────────────────────────────────────────

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('main.register'))

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                        (name, email, hashed))
            mysql.connection.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('main.login'))
        except:
            flash('Email already exists!', 'danger')
        finally:
            cur.close()

    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            from app.models import User
            user_obj = User(user['id'], user['name'], user['email'], user['is_admin'])
            from flask_login import login_user
            login_user(user_obj)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password!', 'danger')

    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    from flask_login import logout_user
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('main.index'))

# ─── ORDERS ───────────────────────────────────────────────

@main.route('/cart')
@login_required
def cart():
    return render_template('cart.html')

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM districts")
    districts = cur.fetchall()

    if request.method == 'POST':
        address = request.form.get('address')
        district_id = request.form.get('district_id')
        delivery_date = request.form.get('delivery_date')
        is_gift = 1 if request.form.get('is_gift') else 0
        receiver_name = request.form.get('receiver_name')
        occasion = request.form.get('occasion')
        message = request.form.get('message')
        cart_items = request.form.get('cart_items')

        cur.execute("SELECT delivery_charge FROM districts WHERE id = %s", (district_id,))
        district = cur.fetchone()
        delivery_charge = district['delivery_charge']

        import json
        items = json.loads(cart_items)
        subtotal = 0
        for item in items:
            cur.execute("SELECT price, stock, name FROM products WHERE id = %s", (item['id'],))
            product = cur.fetchone()
            if product['stock'] < item['quantity']:
                flash(f"Sorry! Only {product['stock']} units of {product['name']} available.", 'danger')
                cur.close()
                return redirect(url_for('main.cart'))
            subtotal += product['price'] * item['quantity']

        total = subtotal + delivery_charge

        cur.execute("""
            INSERT INTO orders (user_id, total, delivery_charge, address, district_id,
            delivery_date, is_gift, receiver_name, occasion, message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, total, delivery_charge, address, district_id,
              delivery_date, is_gift, receiver_name, occasion, message))
        mysql.connection.commit()
        order_id = cur.lastrowid

        for item in items:
            cur.execute("SELECT price, stock FROM products WHERE id = %s", (item['id'],))
            product = cur.fetchone()
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['id'], item['quantity'], product['price']))
            cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s",
                        (item['quantity'], item['id']))
        mysql.connection.commit()
        cur.close()

        send_order_email(current_user.email, current_user.name, order_id, 'confirmed')
        flash('Order placed successfully! 🎉', 'success')
        return redirect(url_for('main.my_orders'))

    cur.close()
    return render_template('checkout.html', districts=districts)

@main.route('/orders')
@login_required
def my_orders():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                (current_user.id,))
    rows = cur.fetchall()
    cur.close()
    result = [dict(row) for row in rows]
    return render_template('orders.html', orders=result)

# ─── ADMIN ────────────────────────────────────────────────

@main.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) as count FROM orders")
    total_orders = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM products")
    total_products = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM users")
    total_users = cur.fetchone()['count']
    cur.close()
    return render_template('admin/dashboard.html',
                           total_orders=total_orders,
                           total_products=total_products,
                           total_users=total_users)

@main.route('/admin/products', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_products():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        stock = request.form.get('stock')
        image = request.files.get('image')

        if image and image.filename != '' and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
        else:
            filename = 'default.jpg'

        cur.execute("""
            INSERT INTO products (name, description, price, category, stock, image)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, description, price, category, stock, filename))
        mysql.connection.commit()
        flash('Product added!', 'success')

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    cur.close()
    return render_template('admin/products.html', products=products)

@main.route('/admin/products/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_product(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM order_items WHERE product_id = %s", (id,))
    cur.execute("DELETE FROM comments WHERE product_id = %s", (id,))
    cur.execute("DELETE FROM products WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Product deleted!', 'success')
    return redirect(url_for('main.admin_products'))

@main.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT orders.*, users.name as user_name
        FROM orders
        JOIN users ON orders.user_id = users.id
        ORDER BY orders.created_at DESC
    """)
    orders = cur.fetchall()
    cur.close()
    return render_template('admin/orders.html', orders=orders)

@main.route('/admin/orders/update/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_update_order(id):
    status = request.form.get('status')
    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, id))
    mysql.connection.commit()
    cur.execute("SELECT orders.*, users.email as user_email, users.name as user_name FROM orders JOIN users ON orders.user_id = users.id WHERE orders.id = %s", (id,))
    order = cur.fetchone()
    send_order_email(order['user_email'], order['user_name'], id, status)
    cur.close()
    flash('Order status updated!', 'success')
    return redirect(url_for('main.admin_orders'))

@main.route('/admin/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_product(id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        stock = request.form.get('stock')
        image = request.files.get('image')

        if image and image.filename != '' and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
            cur.execute("""
                UPDATE products SET name=%s, description=%s, price=%s,
                category=%s, stock=%s, image=%s WHERE id=%s
            """, (name, description, price, category, stock, filename, id))
        else:
            cur.execute("""
                UPDATE products SET name=%s, description=%s, price=%s,
                category=%s, stock=%s WHERE id=%s
            """, (name, description, price, category, stock, id))

        mysql.connection.commit()
        cur.close()
        flash('Product updated!', 'success')
        return redirect(url_for('main.admin_products'))

    cur.execute("SELECT * FROM products WHERE id = %s", (id,))
    product = cur.fetchone()
    cur.close()
    return render_template('admin/edit_product.html', product=product)

@main.route('/api/products')
def api_products():
    ids = request.args.get('ids', '')
    if not ids:
        return jsonify([])
    id_list = ids.split(',')
    cur = mysql.connection.cursor()
    format_strings = ','.join(['%s'] * len(id_list))
    cur.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", id_list)
    products = cur.fetchall()
    cur.close()
    result = []
    for p in products:
        result.append({
            'id': p['id'],
            'name': p['name'],
            'price': float(p['price']),
            'image': p['image']
        })
    return jsonify(result)

@main.route('/orders/cancel/<int:id>', methods=['POST'])
@login_required
def cancel_order(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM orders WHERE id = %s AND user_id = %s", (id, current_user.id))
    order = cur.fetchone()
    if order and order['status'] == 'confirmed':
        cur.execute("UPDATE orders SET status = 'cancelled' WHERE id = %s", (id,))
        mysql.connection.commit()
        flash('Order cancelled successfully.', 'success')
    else:
        flash('This order cannot be cancelled.', 'danger')
    cur.close()
    return redirect(url_for('main.my_orders'))

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            if password:
                hashed = bcrypt.generate_password_hash(password).decode('utf-8')
                cur.execute("UPDATE users SET name=%s, email=%s, password=%s WHERE id=%s",
                            (name, email, hashed, current_user.id))
            else:
                cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s",
                            (name, email, current_user.id))
            mysql.connection.commit()
            flash('Profile updated successfully!', 'success')
        except:
            flash('Email already in use!', 'danger')
        finally:
            cur.close()
        return redirect(url_for('main.profile'))
    cur.execute("SELECT * FROM users WHERE id=%s", (current_user.id,))
    user = cur.fetchone()
    cur.close()
    return render_template('profile.html', user=user)