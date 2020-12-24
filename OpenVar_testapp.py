import os
import sys
import uuid
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)

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
def upload_file_chunked(filename=None):
    #Check if there is content length information in request.headers
    print('Checking Content-Length...')
    if "Content-Length" not in request.headers:
        add_flash_message("Did not sense Content-Length in headers")
        return 'The length of the file could not be read. Please check your file. If the problem persists, please contact us.'
    print("Content is: " + request.headers['Content-Length'] + " bytes")
    
    if int(request.headers['Content-Length']) != 0:
        #If file is not empty, we give it a unique user id, that will be kept for the analysis of this input file
        print("Generating guid...")
        guid = str(uuid.uuid4()) #Generates a uuid of version 4 as specified in RFC 4122
        print("GUID is: " + guid)


        if int(request.headers['Content-Length']) > 10240:
            if int(request.headers['Content-Length']) > app.config['MAX_CONTENT_LENGTH']:
                add_flash_message("File exceeds maximum size")
                return "Uploads are limited to 2GB. For larger files, please contact us."
            filename = guid + '.txt'
            if (filename is None) or (filename == ''):
                add_flash_message("Error with filename")
                return "Error when generating the filename. Please contact us if the error persists."

            print("Initiating chunking...")
            print("Total Content-Length: " + request.headers['Content-Length'])
            upload_full_path = os.path.join(app.config['UPLOAD_PATH'], filename)
            print('Starting chunks...')
            chunk_size = app.config['CHUNK_SIZE']
            try:
                with open(upload_full_path, 'wb') as f:
                    this_is_the_end = False
                    while not this_is_the_end:
                        chunk = request.stream.read(chunk_size)
                        if len(chunk) == 0:
                            this_is_the_end = True
                        else:
                            sys.stdout.write(".")
                            sys.stdout.flush()
                            f.write(chunk)
                            f.flush()
            except OSError as e:
                add_flash_message("Error writing file " + filename + " to disk: " + StringIO(str(e)).getvalue())
                return 'Error when writing the file. Please contact us if the error persists.'
        else:
            upload = request.files['file']
            filename = guid + '.txt'
            if (filename is None) or (filename == ''):
                add_flash_message("Error with filename")
                return "Error when generating the filename. Please contact us if the error persists."
            else:
                upload.save(os.path.join(app.config['UPLOAD_PATH'], filename))

        print("")
        add_flash_message("Success uploading the given file.")
        return '', 204
    
    else:
        return "The selected file appears to be empty. Please check."

@app.errorhandler(413)
def too_large(e):
    return "File is too large", 413

@app.errorhandler(OSError)
def handle_oserror(oserror):
    """Flask framework uses this function if the OSError is not handled by other routes"""
    response = jsonify({"message":StringIO(str(oserror)).getvalue()})
    response.status_code = 500
    return response

def add_flash_message(msg):
    """Provides message to user in browser"""
    print(msg)
    flash(msg)

if __name__ == '__main__':
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024    # 2Gb limit
    app.config['CHUNK_SIZE'] = 10240
    app.config['UPLOAD_EXTENSIONS'] = ['.txt', '.tsv', '.csv']
    app.config['UPLOAD_PATH'] = 'uploads'
    app.secret_key = 'abcd1234'
    port = int(os.getenv("PORT", 5000))
    app.run(host = '0.0.0.0', port=port)

