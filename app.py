from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_login import (
        LoginManager,
        login_user,
        logout_user,
        login_required,
        current_user
    )

from functools import wraps
from config import Config
from models import db, User, Employee, Product, Sale, Expense
from sqlalchemy import func
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import request


    # ==========================================
    # APP CONFIGURATION
    # ==========================================

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


    # ==========================================
    # ROLE ACCESS CONTROL
    # ==========================================

def admin_required(func):
        @wraps(func)
        @login_required
        def decorated_view(*args, **kwargs):

            if current_user.role != "admin":
                flash("Access denied! Admin permission required.", "danger")
                return redirect(url_for("dashboard"))

            return func(*args, **kwargs)

        return decorated_view


    # ==========================================
    # USER LOADER
    # ==========================================

@login_manager.user_loader
def load_user(user_id):
        return db.session.get(User, int(user_id))


    # ==========================================
    # HOME
    # ==========================================

@app.route("/")
def home():

        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))


    # ==========================================
    # REGISTER
    # ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name or not email or not password:
                flash("Please fill in all fields.", "danger")

            elif User.query.filter_by(email=email).first():
                flash("Email already registered.", "danger")

            else:

                # New users always receive employee role
                user = User(
                    name=name,
                    email=email,
                    role="employee"
                )

                user.set_password(password)

                db.session.add(user)
                db.session.commit()

                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))

        return render_template("login.html", register_mode=True)


    # ==========================================
    # LOGIN
    # ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

        if request.method == "POST":

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):

                login_user(user)
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")

        return render_template("login.html", register_mode=False)


    # ==========================================
    # DASHBOARD
    # Admin + Employee
    # ==========================================


@app.route("/dashboard")
@login_required
def dashboard():

        from sqlalchemy import func, extract
        from datetime import datetime

        stats = {
            "employees": Employee.query.count(),
            "products": Product.query.count(),
            "sales": Sale.query.count(),
            "expenses": Expense.query.count()
        }

        current_year = datetime.now().year

        period = request.args.get("period", "monthly")
        selected_year = request.args.get("year", current_year, type=int)

        if period not in ["monthly", "yearly"]:
            period = "monthly"

        if period == "monthly":

            monthly_sales = (
                db.session.query(
                    extract("month", Sale.sale_date),
                    func.sum(Sale.total_amount)
                )
                .filter(extract("year", Sale.sale_date) == selected_year)
                .group_by(extract("month", Sale.sale_date))
                .all()
            )

            monthly_expenses = (
                db.session.query(
                    extract("month", Expense.expense_date),
                    func.sum(Expense.amount)
                )
                .filter(extract("year", Expense.expense_date) == selected_year)
                .group_by(extract("month", Expense.expense_date))
                .all()
            )

            chart_labels = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
            ]

            sales_data = [0.0] * 12
            expenses_data = [0.0] * 12

            for month, total in monthly_sales:
                sales_data[int(month) - 1] = float(total or 0)

            for month, total in monthly_expenses:
                expenses_data[int(month) - 1] = float(total or 0)

        else:

            years = list(range(current_year - 4, current_year + 1))

            chart_labels = [str(year) for year in years]

            yearly_sales = (
                db.session.query(
                    extract("year", Sale.sale_date),
                    func.sum(Sale.total_amount)
                )
                .filter(extract("year", Sale.sale_date).between(years[0], years[-1]))
                .group_by(extract("year", Sale.sale_date))
                .all()
            )

            yearly_expenses = (
                db.session.query(
                    extract("year", Expense.expense_date),
                    func.sum(Expense.amount)
                )
                .filter(extract("year", Expense.expense_date).between(years[0], years[-1]))
                .group_by(extract("year", Expense.expense_date))
                .all()
            )

            sales_data = [0.0] * len(years)
            expenses_data = [0.0] * len(years)

            for year, total in yearly_sales:
                sales_data[int(year) - years[0]] = float(total or 0)

            for year, total in yearly_expenses:
                expenses_data[int(year) - years[0]] = float(total or 0)

        return render_template(
            "dashboard.html",
            stats=stats,
            sales_data=sales_data,
            expenses_data=expenses_data,
            chart_labels=chart_labels,
            period=period,
            selected_year=selected_year,
            current_year=current_year
        )


    # ==========================================
    # USER ROLE MANAGEMENT
    # Admin Only
    # ==========================================

@app.route("/users")
@admin_required
def users():

        all_users = User.query.order_by(User.id.desc()).all()

        return render_template("users.html", users=all_users)


    # ==========================================
    # UPDATE USER ROLE
    # Admin Only
    # ==========================================

@app.route("/update-role/<int:user_id>", methods=["POST"])
@admin_required
def update_role(user_id):

        user = db.session.get(User, user_id)

        if user is None:
            flash("User not found.", "danger")
            return redirect(url_for("users"))

        new_role = request.form.get("role")

        if new_role not in ["admin", "employee"]:
            flash("Invalid role selected!", "danger")
            return redirect(url_for("users"))

        # Prevent changing own role
        if user.id == current_user.id:
            flash("You cannot change your own role!", "warning")
            return redirect(url_for("users"))

        # Prevent removing the last administrator
        if user.role == "admin" and new_role == "employee":

            admin_count = User.query.filter_by(role="admin").count()

            if admin_count <= 1:
                flash("At least one Admin account is required.", "danger")
                return redirect(url_for("users"))

        user.role = new_role
        db.session.commit()

        flash("User role updated successfully!", "success")

        return redirect(url_for("users"))


    # ==========================================
    # LOGOUT
    # ==========================================

@app.route("/logout")
@login_required
def logout():

        logout_user()

        flash("You have been logged out.", "success")

        return redirect(url_for("login"))

        
    # ==========================================
    # EMPLOYEE MANAGEMENT
    # Admin Only
    # ==========================================

@app.route("/employees")
@admin_required
def employees():

        all_employees = Employee.query.order_by(
            Employee.id.desc()
        ).all()

        return render_template("employees.html", employees=all_employees)


    # ADD EMPLOYEE
@app.route("/employees/add", methods=["GET", "POST"])
@admin_required
def add_employee():

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            department = request.form.get("department", "").strip()
            position = request.form.get("position", "").strip()

            try:
                salary = float(request.form.get("salary", "0"))

                if salary < 0:
                    raise ValueError

            except ValueError:
                flash("Please enter a valid salary.", "danger")
                return redirect(url_for("add_employee"))

            if not name or not email:
                flash("Name and email are required.", "danger")
                return redirect(url_for("add_employee"))

            if Employee.query.filter_by(email=email).first():
                flash("Employee email already exists.", "danger")
                return redirect(url_for("add_employee"))

            employee = Employee(
                name=name,
                email=email,
                department=department,
                position=position,
                salary=salary
            )

            db.session.add(employee)
            db.session.commit()

            flash("Employee added successfully!", "success")

            return redirect(url_for("employees"))

        return render_template("add_employee.html")


# EDIT EMPLOYEE
@app.route("/employees/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_employee(id):

    employee = db.session.get(Employee, id)

    if employee is None:
        flash("Employee not found.", "danger")
        return redirect(url_for("employees"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "").strip()
        position = request.form.get("position", "").strip()

        try:
            salary = float(request.form.get("salary", "0"))

            if salary < 0:
                raise ValueError

        except ValueError:
            flash("Please enter a valid salary.", "danger")
            return redirect(url_for("edit_employee", id=id))

        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("edit_employee", id=id))

        existing_employee = Employee.query.filter(
            Employee.email == email,
            Employee.id != id
        ).first()

        if existing_employee:
            flash("Email already exists for another employee.", "danger")
            return redirect(url_for("edit_employee", id=id))

        employee.name = name
        employee.email = email
        employee.department = department
        employee.position = position
        employee.salary = salary

        db.session.commit()

        flash("Employee updated successfully!", "success")

        return redirect(url_for("employees"))

    return render_template("edit_employee.html", employee=employee)

    # DELETE EMPLOYEE
@app.route("/employees/delete/<int:id>", methods=["POST"])
@admin_required
def delete_employee(id):

        employee = db.session.get(Employee, id)

        if employee is None:
            flash("Employee not found.", "danger")
            return redirect(url_for("employees"))

        db.session.delete(employee)
        db.session.commit()

        flash("Employee deleted successfully!", "success")

        return redirect(url_for("employees"))


    # ==========================================
    # INVENTORY MANAGEMENT
    # Admin + Employee
    # ==========================================

    # VIEW PRODUCTS
@app.route("/products")
@login_required
def products():

        all_products = Product.query.order_by(
            Product.id.desc()
        ).all()

        return render_template("products.html", products=all_products)


    # ADD PRODUCT
@app.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()

            try:
                quantity = int(request.form.get("quantity", "0"))
                price = float(request.form.get("price", "0"))

                if quantity < 0 or price < 0:
                    raise ValueError

            except ValueError:
                flash("Please enter valid quantity and price.", "danger")
                return redirect(url_for("add_product"))

            if not name:
                flash("Product name is required.", "danger")
                return redirect(url_for("add_product"))

            product = Product(
                name=name,
                category=category,
                quantity=quantity,
                price=price
            )

            db.session.add(product)
            db.session.commit()

            flash("Product added successfully!", "success")

            return redirect(url_for("products"))

        return render_template("add_product.html")


    # EDIT PRODUCT
@app.route("/products/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_product(id):

        product = db.session.get(Product, id)

        if product is None:
            flash("Product not found.", "danger")
            return redirect(url_for("products"))

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()

            try:
                quantity = int(request.form.get("quantity", "0"))
                price = float(request.form.get("price", "0"))

                if quantity < 0 or price < 0:
                    raise ValueError

            except ValueError:
                flash("Please enter valid quantity and price.", "danger")
                return redirect(url_for("edit_product", id=id))

            if not name:
                flash("Product name is required.", "danger")
                return redirect(url_for("edit_product", id=id))

            product.name = name
            product.category = category
            product.quantity = quantity
            product.price = price

            db.session.commit()

            flash("Product updated successfully!", "success")

            return redirect(url_for("products"))

        return render_template("edit_product.html", product=product)


    # DELETE PRODUCT
@app.route("/products/delete/<int:id>", methods=["POST"])
@login_required
def delete_product(id):

        product = db.session.get(Product, id)

        if product is None:
            flash("Product not found.", "danger")
            return redirect(url_for("products"))

        db.session.delete(product)
        db.session.commit()

        flash("Product deleted successfully!", "success")

        return redirect(url_for("products"))


    # ==========================================
    # SALES MANAGEMENT
    # Admin + Employee
    # ==========================================

    # VIEW SALES
@app.route("/sales")
@login_required
def sales():

        all_sales = Sale.query.order_by(
            Sale.sale_date.desc()
        ).all()

        return render_template("sales.html", sales=all_sales)


    # ADD SALE
@app.route("/sales/add", methods=["GET", "POST"])
@login_required
def add_sale():

        products = Product.query.order_by(Product.name).all()

        if request.method == "POST":

            try:
                product_id = int(request.form.get("product_id", "0"))
                quantity = int(request.form.get("quantity", "0"))

                if quantity <= 0:
                    raise ValueError

            except ValueError:
                flash("Please enter a valid quantity.", "danger")
                return redirect(url_for("add_sale"))

            product = db.session.get(Product, product_id)

            if product is None:
                flash("Please select a valid product.", "danger")
                return redirect(url_for("add_sale"))

            if product.quantity < quantity:
                flash("Insufficient stock available.", "danger")
                return redirect(url_for("add_sale"))

            total_amount = product.price * quantity

            sale = Sale(
                product_id=product.id,
                quantity=quantity,
                total_amount=total_amount
            )

            product.quantity -= quantity

            db.session.add(sale)
            db.session.commit()

            flash("Sale recorded successfully!", "success")

            return redirect(url_for("sales"))

        return render_template("add_sale.html", products=products)


    # ==========================================
    # EXPENSE MANAGEMENT
    # Admin Only
    # ==========================================

    # VIEW EXPENSES
@app.route("/expenses")
@admin_required
def expenses():

        all_expenses = Expense.query.order_by(
            Expense.expense_date.desc()
        ).all()

        return render_template("expenses.html", expenses=all_expenses)


    # ADD EXPENSE
@app.route("/expenses/add", methods=["GET", "POST"])
@admin_required
def add_expense():

        if request.method == "POST":

            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()

            try:
                amount = float(request.form.get("amount", "0"))

                if amount <= 0:
                    raise ValueError

            except ValueError:
                flash("Please enter a valid expense amount.", "danger")
                return redirect(url_for("add_expense"))

            if not title or not category:
                flash("Title and category are required.", "danger")
                return redirect(url_for("add_expense"))

            expense = Expense(
                title=title,
                category=category,
                amount=amount,
                description=description
            )

            db.session.add(expense)
            db.session.commit()

            flash("Expense added successfully!", "success")

            return redirect(url_for("expenses"))

        return render_template("add_expense.html")


    # ==========================================
    # REPORTS MANAGEMENT
    # Admin Only
    # ==========================================

@app.route("/reports")
@admin_required
def reports():

        all_employees = Employee.query.order_by(
            Employee.name
        ).all()

        all_sales = Sale.query.order_by(
            Sale.sale_date.desc()
        ).all()

        all_expenses = Expense.query.order_by(
            Expense.expense_date.desc()
        ).all()

        total_revenue = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).scalar()

        total_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).scalar()

        return render_template(
            "reports.html",
            employees=all_employees,
            sales=all_sales,
            expenses=all_expenses,
            total_revenue=total_revenue,
            total_expenses=total_expenses
        )


    # ==========================================
    # EXPORT REPORTS AS PDF
    # Admin Only
    # ==========================================

@app.route("/reports/pdf/<report_type>")
@admin_required
def export_report_pdf(report_type):

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=25,
            leftMargin=25,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()
        elements = []

        elements.append(
            Paragraph(f"{report_type.title()} Report", styles["Title"])
        )

        elements.append(Spacer(1, 20))

        if report_type == "employees":

            data = [[
                "ID", "Name", "Email",
                "Department", "Position", "Salary"
            ]]

            for emp in Employee.query.order_by(Employee.name).all():

                data.append([
                    str(emp.id),
                    emp.name,
                    emp.email,
                    emp.department or "-",
                    emp.position or "-",
                    f"Rs. {emp.salary or 0:.2f}"
                ])

        elif report_type == "sales":

            data = [[
                "ID", "Product", "Quantity",
                "Total Amount", "Date"
            ]]

            for sale in Sale.query.order_by(
                Sale.sale_date.desc()
            ).all():

                data.append([
                    str(sale.id),
                    sale.product.name if sale.product else "Deleted Product",
                    str(sale.quantity),
                    f"Rs. {sale.total_amount:.2f}",
                    sale.sale_date.strftime("%d-%m-%Y")
                ])

        elif report_type == "expenses":

            data = [[
                "ID", "Title", "Category",
                "Amount", "Date"
            ]]

            for expense in Expense.query.order_by(
                Expense.expense_date.desc()
            ).all():

                data.append([
                    str(expense.id),
                    expense.title,
                    expense.category or "-",
                    f"Rs. {expense.amount:.2f}",
                    expense.expense_date.strftime("%d-%m-%Y")
                ])

        else:
            flash("Invalid report type.", "danger")
            return redirect(url_for("reports"))

        table = Table(data, repeatRows=1)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)

        doc.build(elements)

        buffer.seek(0)

        response = make_response(buffer.getvalue())

        response.headers["Content-Type"] = "application/pdf"

        response.headers["Content-Disposition"] = (
            f"attachment; filename={report_type}_report.pdf"
        )

        return response


    # ==========================================
    # BUSINESS ANALYTICS
    # Admin Only
    # ==========================================

@app.route("/analytics")
@admin_required
def analytics():

        total_revenue = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).scalar()

        total_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).scalar()

        net_profit = total_revenue - total_expenses

        monthly_sales = db.session.query(
            func.strftime("%Y-%m", Sale.sale_date).label("month"),
            func.sum(Sale.total_amount).label("total")
        ).group_by("month").order_by("month").all()

        expense_categories = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label("total")
        ).group_by(Expense.category).all()

        return render_template(
            "analytics.html",
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_profit=net_profit,
            monthly_sales=monthly_sales,
            expense_categories=expense_categories
        )


    # ==========================================
    # 404 ERROR
    # ==========================================

@app.errorhandler(404)
def not_found(error):

        return "Page not found", 404


    # ==========================================
    # CREATE DATABASE TABLES
    # ==========================================

with app.app_context():
        db.create_all()


    # ==========================================
    # RUN APPLICATION
    # ==========================================

if __name__ == "__main__":
        app.run(debug=True)
