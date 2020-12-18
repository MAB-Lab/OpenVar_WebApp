import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.txt', '.tsv', '.csv']
app.config['UPLOAD_PATH'] = 'uploads'

@app.route('/', methods=["GET"])
def home():
    return render_template("Home.html")

@app.route("/help")
def help():
    return render_template("OPVar_help.html")
    
@app.route("/submit", methods=['GET'])
def submit():
    print(request.form)
    return render_template("OPVar_submit.html")

@app.route("/submit", methods=["POST"])
def upload_file():
    print('Starting upload')
    uploaded = request.files['file']
    upload_name = secure_filename(uploaded.filename)
    if upload_name != '':
        ext = os.path.splitext(upload_name)[1]
        if ext not in app.config['UPLOAD_EXTENSIONS']:
            return 'Invalid file format.'
        else:
            uploaded.save(os.path.join(app.config['UPLOAD_PATH'], upload_name))
            return '', 204
    else:
        return 'ERROR: not file selected'

@app.errorhandler(413)
def too_large(e):
    return "File is too large", 413

if __name__ == '__main__':
    app.run(host = '0.0.0.0')

