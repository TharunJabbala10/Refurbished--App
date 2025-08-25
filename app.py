from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from models import db, Phone
import pandas as pd
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "supersecret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phones.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

USER = {"admin": "password"}

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in USER and USER[username] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    phones = Phone.query.all()
    return render_template("dashboard.html", phones=phones)

@app.route("/add", methods=["GET", "POST"])
def add_phone():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        brand = request.form["brand"]
        model = request.form["model"]
        condition = request.form["condition"]
        base_price = float(request.form["price"])
        stock = int(request.form["stock"])
        phone = Phone(brand=brand, model=model, condition=condition,
                      base_price=base_price, stock=stock)
        db.session.add(phone)
        db.session.commit()
        flash("Phone added successfully!")
        return redirect(url_for("dashboard"))
    return render_template("add_phone.html")

@app.route("/delete/<int:id>")
def delete_phone(id):
    if "user" not in session:
        return redirect(url_for("login"))
    phone = Phone.query.get_or_404(id)
    db.session.delete(phone)
    db.session.commit()
    flash("Phone deleted successfully")
    return redirect(url_for("dashboard"))

@app.route("/bulk_upload", methods=["GET", "POST"])
def bulk_upload():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        file = request.files["file"]
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file)
            for _, row in df.iterrows():
                phone = Phone(
                    brand=row["brand"],
                    model=row["model"],
                    condition=row["condition"],
                    base_price=row["base_price"],
                    stock=row["stock"]
                )
                db.session.add(phone)
            db.session.commit()
            flash("Bulk upload complete!")
            return redirect(url_for("dashboard"))
        else:
            flash("Only CSV files allowed")
    return render_template("bulk_upload.html")

@app.route("/inventory")
def inventory():
    if "user" not in session:
        return redirect(url_for("login"))
    query = request.args.get("q")
    phones = Phone.query
    if query:
        phones = phones.filter((Phone.model.contains(query)) | (Phone.brand.contains(query)))
    phones = phones.all()
    return render_template("inventory.html", phones=phones)

def map_condition(platform, condition):
    if platform == "apit":
        mapping = {"New": "New", "Good": "Good", "Scrap": "Scrap"}
    elif platform == "clue":
        mapping = {"New": "3 stars (Excellent)", "Good": "2 stars (Good)", "Scrap": "1 star (Usable)"}
    elif platform == "raptor":
        mapping = {"New": "New", "Good": "Good", "Scrap": "As New"}
    return mapping.get(condition, "Unsupported")

@app.route("/list/<platform>/<int:id>")
def list_phone(platform, id):
    if "user" not in session:
        return redirect(url_for("login"))
    phone = Phone.query.get_or_404(id)
    if phone.stock <= 0:
        flash(f"{phone.model} cannot be listed on {platform.title()} (Out of Stock)")
        return redirect(url_for("dashboard"))
    if platform == "apit":
        price = phone.price_apit()
    elif platform == "clue":
        price = phone.price_clue()
    elif platform == "raptor":
        price = phone.price_raptor()
    else:
        flash("Invalid platform")
        return redirect(url_for("dashboard"))
    if price <= 0:
        flash(f"Listing failed: {phone.model} is unprofitable on {platform.title()}")
        return redirect(url_for("dashboard"))
    mapped_condition = map_condition(platform, phone.condition)
    if mapped_condition == "Unsupported":
        flash(f"Listing failed: Condition not supported on {platform.title()}")
        return redirect(url_for("dashboard"))
    if platform not in (phone.listed_on or ""):
        phone.listed_on = (phone.listed_on + "," + platform).strip(",")
        db.session.commit()
    flash(f" {phone.model} listed successfully on {platform.title()} "
          f"as '{mapped_condition}' at ${price}")
    return redirect(url_for("dashboard"))

@app.route("/listing_report")
def listing_report():
    if "user" not in session:
        return redirect(url_for("login"))
    phones = Phone.query.filter(Phone.listed_on != "").all()
    return render_template("listing_report.html", phones=phones)

@app.route("/download_listing_pdf")
def download_listing_pdf():
    if "user" not in session:
        return redirect(url_for("login"))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    title = Paragraph("Listing Report - Refurbished Phones", styles['Title'])
    elements.append(title)
    data = [["Brand", "Model", "Condition", "Base Price", "Stock", "Listed Platforms",
             "Apit Price", "Clue Price", "Raptor Price"]]
    phones = Phone.query.filter(Phone.listed_on != "").all()
    for p in phones:
        data.append([p.brand, p.model, p.condition, str(p.base_price),
                     str(p.stock), p.listed_on,
                     str(p.price_apit()), str(p.price_clue()), str(p.price_raptor())])
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.gray),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="listing_report.pdf", mimetype="application/pdf")
if __name__ == "__main__":
    app.run(debug=True)