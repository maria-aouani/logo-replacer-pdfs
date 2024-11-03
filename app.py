from flask import Flask, request, send_file, render_template, url_for
import fitz
import pymupdf # PyMuPDF
import io
from PIL import Image
import os

app = Flask(__name__)

'''
@app.route('/')
def login():

    return render_template('login.html')
'''

@app.route('/files')
def restore_file():

    return render_template('files.html')

@app.route('/upload')
def index():
    return render_template('upload.html')


@app.route('/download', methods=['POST'])
def upload_file():
    pdf_file = request.files['pdf']
    new_logo = request.files['logo']

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

    # Ensure the static directory exists
    if not os.path.exists("static"):
        os.makedirs("static")

    # Save the PDF to a static file to serve to the user
    with open("static/updated_logo.pdf", "wb") as f:
        f.write(output_pdf.read())

    return render_template('download.html', download_url=url_for('static', filename='updated_logo.pdf'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
