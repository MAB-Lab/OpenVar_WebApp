import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.txt', '.tsv', '.csv']
app.config['UPLOAD_PATH'] = 'uploads'

@app.route('/', methods=["GET", "POST"])
def home():
    return render_template("Home.html")

@app.route("/help")
def help():
    return render_template("OPVar_help.html")
    
@app.route("/submit", methods=['GET'])
def submit():
    print(request.form)
    return render_template("OPVar_submit.html")

@app.errorhandler(413)
def too_large(e):
    return "File is too large", 413

if __name__ == '__main__':
    app.run(host = '0.0.0.0')

