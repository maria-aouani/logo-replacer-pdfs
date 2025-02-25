from flask import Flask, request, send_file, render_template, url_for, redirect, flash, session
from flask_wtf.file import FileField
from wtforms import SubmitField, StringField, PasswordField
from flask_wtf import Form, FlaskForm
import fitz
import pymupdf  # PyMuPDF
from pymupdf import Document
import io
from PIL import Image
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.validators import DataRequired, EqualTo

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for using Flask-WTF forms

# Save logo in static directory
def save_logo_static(file):
    user_id = session.get("user_id")
    logo_filename = f"{user_id}_uploaded_logo.png"
    logo_path = os.path.join('static', logo_filename)
    file.save(logo_path)

    # Сохраните путь к логотипу в базе данных
    conn = sqlite3.connect("LogoReplacer.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE my_files SET logo_path = ? WHERE user_id = ?", (logo_path, user_id))
    conn.commit()
    conn.close()
    return logo_path



# Database initialization function
def init_db():
    conn = sqlite3.connect("LogoReplacer.db")
    cursor = conn.cursor()
    # Create the my_files table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS my_files (name TEXT, file_data BLOB, user_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/files', methods=["GET", "POST"])
def restore_filerestore_file():
    if "user_id" not in session:
        flash("Please log in to access your files.", "warning")
        return (redirect(url_for("login")))

    if request.method == "POST":
        file_id = request.form.get('file_id')
        if file_id:
            conn = sqlite3.connect("LogoReplacer.db")
            cursor = conn.cursor()
            cursor.execute("SELECT name, file_data FROM my_files WHERE rowid = ? AND user_id = ?", (file_id, session['user_id']))
            file_record = cursor.fetchone()
            conn.close()

            if file_record:
                name_v, data_v = file_record
                return send_file(io.BytesIO(data_v), download_name=name_v, as_attachment=True)

    # Get list of files in the database to display
    conn = sqlite3.connect("LogoReplacer.db")
    cursor = conn.cursor()
    cursor.execute("SELECT rowid, name, logo_path FROM my_files WHERE user_id = ?", (session["user_id"],))
    files = cursor.fetchall()

    conn.close()

    return render_template('files.html', files=files)

@app.route('/upload', methods=["GET", "POST"])
def upload():
    form = UploadForm()
    user_id = session.get("user_id")
    logo_filename = f"{user_id}_uploaded_logo.png"
    logo_path = os.path.join('static', logo_filename)

    if request.method == "POST" and form.validate_on_submit():
        # Check if PDF file was uploaded
        pdf_file = request.files.get('pdf')
        logo_file = request.files.get('logo')

        # Save the logo if provided, otherwise use existing logo if available
        if logo_file:
            logo_path = save_logo_static(logo_file)
            flash("New logo uploaded and saved.", "success")
        elif not os.path.exists(logo_path):
            flash("Please upload a logo first.", "danger")
            return redirect(url_for('upload'))

        # Process PDF with existing or newly uploaded logo
        if pdf_file:
            pdf_document = pymupdf.Document(stream=pdf_file.read(), filetype="pdf")
            logo_image = Image.open(logo_path)

            # Convert logo to byte stream for insertion
            logo_bytes = io.BytesIO()
            logo_image.save(logo_bytes, format='PNG')
            logo_bytes = logo_bytes.getvalue()

            # Insert logo in the first page of PDF
            first_page = pdf_document.load_page(0)
            for img_index, img in enumerate(first_page.get_images(full=True)):
                xref = img[0]
                img_rect = first_page.get_image_rects(xref)[0]
                first_page.delete_image(xref)
                first_page.insert_image(img_rect, stream=logo_bytes)
                break

            # Save the modified PDF to a bytes buffer
            output_pdf = io.BytesIO()
            pdf_document.save(output_pdf)
            pdf_document.close()
            output_pdf.seek(0)

            # Send modified PDF as download
            updated_filename = f"{pdf_file.filename.rsplit('.', 1)[0]}_updated.pdf"
            return send_file(output_pdf, mimetype='application/pdf', download_name=updated_filename, as_attachment=True)

        flash("Upload a PDF to proceed.", "warning")
    return render_template('upload.html', form=form)

@app.route('/download', methods=['POST'])
def upload_file():
    pdf_file = request.files['pdf']
    new_logo = request.files['logo']

    # Save the new logo in the static folder
    if new_logo:
        user_id = session.get("user_id")
        if not os.path.exists("static/logos"):
            os.makedirs("static/logos")
        logo_filename = f"logo_{user_id}.png"
        logo_path = os.path.join("static", "logos", logo_filename)
        new_logo.save(logo_path)

    # Load the PDF with PyMuPDF
    pdf_document = pymupdf.open(stream=pdf_file.read(), filetype="pdf")

    # Load the new logo with Pillow
    new_logo_image = Image.open(new_logo)
    new_logo_bytes = io.BytesIO()
    new_logo_image.save(new_logo_bytes, format='PNG')
    new_logo_bytes = new_logo_bytes.getvalue()

    # Iterate through the pages and replace the logo on the first page
    first_page = pdf_document.load_page(0)

    # Assuming logo is an image, iterate through all images on the page
    for img_index, img in enumerate(first_page.get_images(full=True)):
        xref = img[0]
        img_rect = first_page.get_image_rects(xref)[0]
        first_page.delete_image(xref)  # Remove the existing image (logo)
        first_page.insert_image(img_rect, stream=new_logo_bytes)
        break

    # Save the modified PDF to a bytes buffer
    output_pdf = io.BytesIO()
    pdf_document.save(output_pdf)
    pdf_document.close()
    output_pdf.seek(0)

    if "user_id" in session:
        # Save the PDF to the SQLite database
        original_filename = pdf_file.filename.rsplit('.', 1)[0]
        updated_filename = f"{original_filename}_updated.pdf"
        pdf_data = output_pdf.getvalue()
        database(name=updated_filename, file_data=pdf_data, user_id=session["user_id"])

        # Return the modified PDF to the user for download
        return send_file(io.BytesIO(pdf_data), mimetype='application/pdf', download_name=updated_filename, as_attachment=True)

    if not os.path.exists("static"):
        os.makedirs("static")

    with open("static/updated_logo.pdf", "wb") as f:
        f.write(output_pdf.getvalue())

    return render_template('download.html', download_url=url_for('static', filename='updated_logo.pdf'))

class UploadForm(FlaskForm):
    pdf = FileField('Upload PDF')
    logo = FileField('Upload Logo')
    submit = SubmitField('Upload')

def database(name, file_data, user_id):
    conn = sqlite3.connect("LogoReplacer.db")
    cursor = conn.cursor()

    # Insert the file into the table
    cursor.execute("ALTER TABLE my_files ADD COLUMN logo_path TEXT")
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("LogoReplacer.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for('upload'))
        else:
            flash("Invalid credentials, please try again.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if request.method == "POST" and form.validate_on_submit():
        username = form.username.data
        password = generate_password_hash(form.password.data)

        conn = sqlite3.connect("LogoReplacer.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Please choose a different one.", "danger")
        finally:
            cursor.close()
            conn.close()
    else:
        if request.method == "POST":
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Error in {field}: {error}", "danger")
            flash("Registration failed. Please try again.", "danger")
    return render_template('signup.html', form=form)

@app.route('/home', methods=["GET", "POST"])
def home():
    return render_template('home.html')


if __name__ == '__main__':
    init_db()  # Initialize the database and create the table if it doesn't exist
    app.run(debug=True, port=5000)
