# Imports
import os
import sys
import uuid
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import StringField, SelectField, FileField, FormField, SubmitField
from wtforms.validators import DataRequired, Email, Length
import dramatiq
from dramatiq.brokers.redis import RedisBroker

import time

# Set up app and broker
app = Flask(__name__)
redis_broker = RedisBroker(host="127.0.0.1")
dramatiq.set_broker(redis_broker)

# Initiate forms
class UploadVCF(FlaskForm):
    vcf = FileField("Please upload a Variant Calling File (VCF):",
            validators = [FileRequired(), FileAllowed(['vcf', 'tsv', 'txt', 'csv'], 'Only accepts .vcf, .tsv, .txt and .csv formats.')])
    
class UserInputForm(FlaskForm):
    email = StringField("Please enter a contact email address:", 
            validators=[DataRequired(), Email()])
    study_name = StringField("Please enter a study name:", 
            validators=[DataRequired(), Length(max=40)])
    species = SelectField("Species:", 
            choices=[("human", "Human"), ("mouse", "Mouse"), ("rat", "Rat"), ("fruit fly", "Fruit fly")], 
            validators=[DataRequired()])
    genome = SelectField("Genome version used in VCF:", 
            choices=[("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19")], 
            validators=[DataRequired()])
    build = SelectField("Genome build to annotate the VCF:", 
            choices=[("OP_Ens", "OpenProt (Ensembl)"), ("OP_RefSeq", "OpenProt (NCBI RefSeq)"), ("Ensembl", "Ensembl (only canonical sequences)"), ("RefSeq", "NCBI RefSeq (only canonical sequences")], 
            validators=[DataRequired()])
    guid = StringField("GUID:")

class CombinedForm(FlaskForm):
    user_input = FormField(UserInputForm)
    file_upload = FormField(UploadVCF)


# dramatiq actors
@dramatiq.actor(max_retries = 2, notify_shutdown=True)
def count_number_guid(guid):
    try:
        n = 0
        time.sleep(5)
        for e in guid:
            if e in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:
                n += 1
            return guid, n
    except Shutdown:
        cleanup()
        raise

@dramatiq.actor(max_retries = 2, notify_shutdown=True)
def generate_new_guid(guid, n):
    try:
        time.sleep(5)
        new_guid = []
        for e in guid:
            if e in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:
                new_guid.append(n)
            else:
                new_guid.append(e)
        guid_results_dir = os.path.join('results', guid)
        if os.path.exists(guid_results_dir):
            return print('Error: duplicated guid. Directory already exists.')
        else:
            os.mkdir(guid_results_dir)
            guid_results_txt = os.path.join(guid_results_dir, 'results.txt')
            with open(guid_results_txt, 'w') as f:
                f.write(guid)
                f.write(n)
                f.write(''.join(new_guid))
                f.flush()
            return print('THE GUID {guid} is transformed to {new_guid}'.format(guid=guid, new_guid = ''.join(new_guid)))
    except Shutdown:
        cleanup()
        raise

#APP ROUTES
# Home page
@app.route('/', methods=["GET"])
def home():
    return render_template("OPV_home.html")

# Help page
@app.route('/help')
def help():
    return render_template("OPV_help.html")

# Submit page
@app.route('/submit', methods=["GET"])
def submit():
    form=CombinedForm()
    form.user_input.genome.choices = [("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19")]
    return render_template("OPV_submit.html", form=form)

# Route for user input form submission
@app.route('/opv_submit', methods=['POST'])
def process_userinput():
    form = CombinedForm(request.form)
    if form.user_input.validate(form.user_input):
        guid = form.user_input.guid.data
        link = '/' + guid
        email = form.user_input.email.data
        study_name = form.user_input.study_name.data
        
        n = str(len(guid))
        generate_new_guid.send(guid, n)

        return jsonify({'outcome': 'success', 'guid': guid, 'link': link, 'email': email, 'study_name': study_name})
    else:
        return jsonify({'outcome': 'error', 'data': form.errors})

# Results page
@app.route('/<guid>')
def get_results(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    if os.path.exists(results_dir):
        results_txt = os.path.join(results_dir, 'results.txt')
        data = []
        with open(results_txt, 'r') as result_file:
            for line in result_file:
                data.append(line)
        message = ' / '.join(data)
        return render_template("OPV_results.html", message = message)
    else:
        message = 'The analysis is still running'
        return render_template("OPV_results.html", message = message)

# Route for upload processing
@app.route('/upload_file', methods=['POST'])
def upload():
    upload = request.files['file']
    if upload:
        submitted_filename = secure_filename(upload.filename)
        if submitted_filename == '':
            return jsonify({'outcome': 'error', 'error': 'No file selected. Please select a file to upload.'})
        elif submitted_filename[-4:] not in app.config['UPLOAD_EXTENSIONS']:
            return jsonify({'outcome': 'error', 'error': 'Only .vcf, .tsv, .txt and .csv formats are accepted.'})
        else:
            #Check if there is content length information in request.headers
            if "Content-Length" not in request.headers:
                return jsonify({'outcome': 'error', 'error': 'The length of the file could not be read, please check your file. If the problem persists, please contact us.'})
            if int(request.headers['Content-Length']) != 0:
                #If file is not empty, we give it a unique user id, that will be kept for the analysis of this input file
                guid = str(uuid.uuid4())
                if int(request.headers['Content-Length']) > 10240:
                    #Check if files necessitates chunking
                    if int(request.headers['Content-Length']) > app.config['MAX_CONTENT_LENGTH']:
                        #Check if over size limit
                        return jsonify({'outcome': 'error', 'error': 'Uploads are limited to 2GB. For larger files, please contact us.'})
                    else:
                        filename = guid + '.vcf'
                        if (filename is None) or (filename == '') or (filename == '.vcf'):
                            return jsonify({'outcome': 'error', 'error': "We're sorry, an internal error occurred. Please contact us if the problem persists"})
                        else:
                            upload_full_path = os.path.join(app.config['UPLOAD_PATH'], filename)
                            chunk_size = app.config['CHUNK_SIZE']
                            try:
                                with open(upload_full_path, 'wb') as f:
                                    this_is_the_end = False
                                    while not this_is_the_end:
                                        chunk = upload.stream.read(chunk_size)
                                        if len(chunk) == 0:
                                            this_is_the_end = True
                                        else:
                                            f.write(chunk)
                                            f.flush()
                                    return jsonify({'outcome': 'success', 'file': submitted_filename, 'guid': guid})
                            except OSError as e:
                                return jsonify({'outcome': 'error', 'error': "Error when writing the file. Please contact us if the error persists."})
                else:
                    #File is small enough to avoid chunking
                    filename = guid + '.vcf'
                    if (filename is None) or (filename == '') or (filename == '.vcf'):
                        return jsonify({'outcome': 'error', 'error': "We're sorry, an internal error occurred. Please contact us if the problem persists"})
                    else:
                        upload.save(os.path.join(app.config['UPLOAD_PATH'], filename))
                        return jsonify({'outcome': 'success', 'file': submitted_filename, 'guid': guid})
            else:
                return jsonify({'outcome': 'error', 'error': 'The selected file appears to be empty. Please check.'})
    else:
        return jsonify({'outcome': 'error', 'error': 'No file was uploaded.'})

# Route for dynamic genome version display
@app.route('/genome/<species>')
def genome(species):
    genomes = {"human": [("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19")], "mouse": [("mm39", "GRCm39 / mm39"), ("mm10", "GRCm38 / mm10")], 
            "rat": [("rn6", "RGSC6.0 / rn6"), ("rn5", "RGSC5.0 / rn5")], "fruit fly": [("dm6", "BDGP R6 / dm6"), ("dm5", "BDGP R5 / dm5")]}
    versionArray = []
    for version_tuple in genomes[species]:
        version = {}
        version['value'] = version_tuple[0]
        version['name'] = version_tuple[1]
        versionArray.append(version)
    return jsonify({'genome_versions': versionArray})

# Routes for error handling
@app.errorhandler(413)
def too_large(e):
    return "File is too large", 413

@app.errorhandler(OSError)
def handle_oserror(oserror):
    """Flask framework uses this function if the OSError is not handled by other routes"""
    response = jsonify({"message":StringIO(str(oserror)).getvalue()})
    response.status_code = 500
    return response


# APP CONFIGURATION
if __name__ == '__main__':
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024    # 2Gb limit
    app.config['CHUNK_SIZE'] = 10240
    app.config['UPLOAD_EXTENSIONS'] = ['.vcf', '.txt', '.tsv', '.csv']
    app.config['UPLOAD_PATH'] = 'uploads'
    app.config['RESULTS_PATH'] = 'results'
    app.secret_key = 'abcd1234'
    port = int(os.getenv("PORT", 5000))
    app.run(host = '0.0.0.0', debug=True, port=port)
