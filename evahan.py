from flask import *
from flask_mysqldb import MySQL
import os
import re
from datetime import datetime
from werkzeug.utils import secure_filename
import qrcode
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'pritishghodake'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '#shubhammmmm_01'
app.config['MYSQL_DB'] = 'evahan'

mysql=MySQL(app)

app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs("uploads", exist_ok=True)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/new')
def home():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM user')
    temp=cursor.fetchall()
    cur_year=datetime.now().year
    print(cur_year)
    return render_template('home.html',now=cur_year)

@app.route('/login', methods=['GET', 'POST'])
def login():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM user')
    user=cursor.fetchall()
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Dummy authentication
        if username == user[0][2] and password == user[0][3]:
            session['user']=username
            return redirect('/')
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route('/preview', methods=['GET', 'POST'])
def pdf():
    return render_template('pdf.html')

@app.route("/save_certificate", methods=["POST"])
def save_certificate():

    form = request.form

    front = request.files.get("front_left")
    back = request.files.get("back_right")
    doc = request.files.get("rc_document")

    front_path = back_path = doc_path = None

    if front:
        filename = secure_filename(front.filename)
        front_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        front.save(front_path)

    if back:
        filename = secure_filename(back.filename)
        back_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        back.save(back_path)

    if doc:
        filename = secure_filename(doc.filename)
        doc_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    

    # -------- REQUIRED VALIDATION -------- #
    required_fields = [
        "cop", "creation_date", "valid_from", "valid_till",
        "vehicle_reg", "owner_name", "mobile",
        "product", "quantity", "chassis" , "cop_valid_till","rto_location"
    ]

    for field in required_fields:
        if not form.get(field):
            flash(f"{field} is required")
            return redirect(url_for("home"))
    
    if not form.get("chassis").isdigit() or len(form.get("chassis")) != 5:
        flash("Chassis number must be exactly 5 digits")
        return redirect(url_for("home"))
    # -------- MOBILE VALIDATION -------- #
    mobile = form.get("mobile")
    if not re.fullmatch(r"[0-9]\d{9}", mobile):
        flash("Invalid mobile number")
        return redirect(url_for("home"))

    # -------- VEHICLE REG VALIDATION -------- #
    vehicle_reg = form.get("vehicle_reg")
    if not re.fullmatch(r'^[A-Z]{2}[0-9]{2}-[A-Z]{1,2}-[0-9]{4}$', vehicle_reg):
        flash("Invalid vehicle registration format")
        return redirect(url_for("home"))

    # -------- DATE VALIDATION -------- #
    try:
        creation_date = datetime.strptime(form.get("creation_date"), "%Y-%m-%d")
        valid_till = datetime.strptime(form.get("valid_till"), "%Y-%m-%d")

        if valid_till.year != creation_date.year + 1:
            flash("Valid till must be 1 year from creation date")
            return redirect(url_for("home"))

    except:
        flash("Invalid date format")
        return redirect(url_for("home"))

    # -------- DUPLICATE CHECK -------- #
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM certificates WHERE vehicle_reg=%s", (vehicle_reg,))
    existing = cur.fetchone()

    if existing:
        flash("Vehicle number already exists")
        cur.close()
        return redirect(url_for("home"))

    # -------- INSERT INTO DATABASE -------- #
    insert_query = """
        INSERT INTO certificates
        (cop, creation_date, valid_from, valid_till,
         vehicle_reg, owner_name, mobile,
         product, quantity, chassis,
         year, vehicle_make, vehicle_model,
         dealer_name, rto_location,cop_valid,passing_rto_loc,front_image, back_image, doc_image)
        VALUES (%s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,%s,%s,%s,%s,%s)
    """

    values = (
        form.get("cop"),
        form.get("creation_date"),
        form.get("valid_from"),
        form.get("valid_till"),
        form.get("vehicle_reg"),
        form.get("owner_name"),
        form.get("mobile"),
        form.get("product"),
        form.get("quantity"),
        form.get("chassis"),
        form.get("year"),
        form.get("make"),
        form.get("model"),
        form.get("dealer_name"),
        form.get("dealer_rto"),
        form.get("cop_valid_till"),
        form.get("rto_location"),
        front_path,
        back_path,
        doc_path,

    )

    cur.execute(insert_query, values)
    mysql.connection.commit()
    certificate_id = cur.lastrowid  # 🔥 IMPORTANT
    certificate_no=str(form.get("rto_location")) + str(certificate_id + 1000)
    cur = mysql.connection.cursor()
    cur.execute("UPDATE certificates SET certificate_no = %s WHERE id = %s",(certificate_no,certificate_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for("preview_certificate", cert_id=certificate_id))

@app.route("/preview/<int:cert_id>")
def preview_certificate(cert_id):

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM certificates WHERE id = %s", (cert_id,))
    certificate = cur.fetchone()
    cur.close()

    verify_url = "https://evhaan.in/preview/"+str(cert_id)

    # Generate QR in memory
    qr = qrcode.make(verify_url)

    buffer = BytesIO()
    qr.save(buffer, format="PNG")

    qr_base64 = base64.b64encode(buffer.getvalue()).decode()


    if not certificate:
        return "Certificate not found"
    print(certificate)
    return render_template("pdf.html", data=certificate,qr=qr_base64)

@app.route("/")
def dashboard():

    search = request.args.get("search")

    cur = mysql.connection.cursor()

    if search:
        cur.execute("""
            SELECT * FROM certificates
            WHERE certificate_no LIKE %s
            OR vehicle_reg LIKE %s
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%"))
    else:
        cur.execute("SELECT * FROM certificates ORDER BY id DESC")

    certificates = cur.fetchall()
    cur.close()

    return render_template("dashboard.html", certificates=certificates)

@app.route("/edit/<int:cert_id>", methods=["GET", "POST"])
def edit_certificate(cert_id):

    cur = mysql.connection.cursor()

    if request.method == "POST":

        update_query = """
            UPDATE certificates SET
            owner_name=%s,
            mobile=%s,
            vehicle_reg=%s,
            product=%s,
            quantity=%s,
            chassis=%s,
            year=%s,
            vehicle_make=%s,
            vehicle_model=%s,
            dealer_name=%s,
            rto_location=%s
            WHERE id=%s
        """

        values = (
            request.form.get("owner_name"),
            request.form.get("mobile"),
            request.form.get("vehicle_reg"),
            request.form.get("product"),
            request.form.get("quantity"),
            request.form.get("chassis"),
            request.form.get("year"),
            request.form.get("vehicle_make"),
            request.form.get("vehicle_model"),
            request.form.get("dealer_name"),
            request.form.get("rto_location"),
            cert_id
        )

        cur.execute(update_query, values)
        mysql.connection.commit()
        cur.close()

        return redirect(url_for("dashboard"))

    # GET method
    cur.execute("SELECT * FROM certificates WHERE id=%s", (cert_id,))
    certificate = cur.fetchone()
    cur.close()

    return render_template("edit.html", data=certificate)

@app.route("/delete/<int:cert_id>")
def delete_certificate(cert_id):

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM certificates WHERE id=%s", (cert_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for("dashboard"))

if __name__ == '__main__':
   app.run(debug = True)

