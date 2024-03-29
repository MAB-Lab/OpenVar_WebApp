# Imports
import os
import sys
import uuid
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import StringField, SelectField, FileField, FormField, SubmitField
from wtforms.validators import DataRequired, Email, Length
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Interrupt
from OpenVar.openvar import SeqStudy, OpenVar, OPVReport
import pickle
import matplotlib.pyplot as plt
from matplotlib.colors import *
import zipfile
import requests
import traceback

# Setup app
app = Flask(__name__, static_url_path='/openvar/static')
if "OPENVAR_SETTINGS_FILE" in os.environ:
    app.config.from_envvar('OPENVAR_SETTINGS_FILE')

# Setup broker
redis_broker = RedisBroker(host="open-var-prod.vhost32")
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
    genome = SelectField("Genome assembly used in VCF:", 
            choices=[("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19"), ("b37", "GRCH37 / b37")], 
            validators=[DataRequired()])
    build = SelectField("Genome build to annotate the VCF:", 
            choices=[("OP_Ensembl", "OpenProt (Ensembl)"), ("OP_RefSeq", "OpenProt (NCBI RefSeq)"), ("Ensembl", "Ensembl (only canonical sequences)"), ("RefSeq", "NCBI RefSeq (only canonical sequences")], validators=[DataRequired()])
    guid = StringField("GUID:")

class CombinedForm(FlaskForm):
    user_input = FormField(UserInputForm)
    file_upload = FormField(UploadVCF)

def wc(filepath):
    f = open(filepath,'r')
    nl = ne = nc = 0
    for line in f:
        nl += 1
        ne = ne + len(line.strip('\n').split('\t'))
        nc = nc + len(line)
    f.close()
    return (nl, ne, nc)

def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, '..')))

def send_email(to, subject, mg_domain, mg_key, plain=None, from_address=None):
    if from_address is None:
        from_address = "notifications@saltorf.com"
    data = {"from": from_address, "to": to, "subject": subject}
    if plain is not None:
        data["text"] = plain
    response = requests.post('https://api.mailgun.net/v2/{}/messages'.format(mg_domain), data=data, auth=('api', mg_key))
    return response.status_code

# dramatiq actors
@dramatiq.actor(max_retries = 0, notify_shutdown=True, time_limit=18000000)
def run_openvar(guid, study_name, species, genome_version, annotation, upload_path, result_path, email, mg_domain, mg_key):
    try:
        print('Launching OpenVar...')
        print('Study name: ' + study_name + ' / Email: ' + email)
        input_file = os.path.join(upload_path, (guid+'.vcf'))
        vcf = SeqStudy(data_dir = upload_path, 
                file_name = (guid + '.vcf'), 
                results_dir = os.path.join(result_path, guid), 
                study_name = study_name, 
                specie = species,
                genome_version = genome_version,
                annotation = annotation,
                picard_path = '/open-var-deposit/picard/')
        if not vcf.file_check:
            print('Writin error file')
            error_file = os.path.join(os.path.join(result_path, guid), 'error.txt')
            with open(error_file, 'w') as f:
                f.write('Your file did not pass the VCF format validation step. Please check your file format before resubmitting the analysis.')
            print('Moving input file...')
            input_file = os.path.join(upload_path, (guid+'.vcf'))
            os.rename(input_file, os.path.join(result_path, 'input_vcf.vcf'))
        elif not vcf.lift_check:
            print('Writin error file')
            error_file = os.path.join(os.path.join(result_path, guid), 'error.txt')
            with open(error_file, 'w') as f:
                f.write('No variants from your input vcf could be lifted over to hg38. Please check the genome version of your input vcf (e.g. hg19 or b37).')
            print('Moving input file...')
            input_file = os.path.join(upload_path, (guid+'.vcf'))
            os.rename(input_file, os.path.join(result_path, 'input_vcf.vcf'))
        else:
            opv = OpenVar(snpeff_path = '/open-var-deposit/snpEff/', 
                    vcf = vcf)
            print('opv object has been created {}'.format(opv.output_dir))
            if "OP_" in annotation:
                run_ok = opv.run_snpeff_parallel_pipe()
            else:
                run_ok = opv.run_snpeff(vcf.single_vcf_path, annotation)
            print('Openvar was run {}'.format(run_ok))
            if not run_ok:
                print('Wrinting error file')
                error_file = os.path.join(os.path.join(result_path, guid), 'error.txt')
                with open(error_file, 'w') as f:
                    f.write("Oops, we're sorry but a fatal error occurred whilst running your analysis. You may try to resubmit, but please contact us should the error persist.")
                print('Moving input file...')
                input_file = os.path.join(upload_path, (guid+'.vcf'))
                os.rename(input_file, os.path.join(result_path, 'input_vcf.vcf'))
            else:
                if wc(input_file) == (wc(os.path.join(opv.output_dir, 'warnings.txt'))[0] - 1):
                    print('Writing error file')
                    error_file = os.path.join(os.path.join(result_path, guid), 'error.txt')
                    with open(error_file, 'w') as f:
                        f.write("All alleles in the submitted vcf were invalid: please check that you selected the right species and/or the right genome version.")
                    print('Moving input file...')
                    input_file = os.path.join(upload_path, (guid+'.vcf'))
                    os.rename(input_file, os.path.join(result_path, 'input_vcf.vcf'))
                else:
                    opvr = OPVReport(opv)
                    print('opvr object created')
                    opvr.aggregate_annotated_vcf()
                    print('aggregate was run')
                    opvr.write_tabular()
                    print('tsv written')
                    if "OP_" in annotation:
                        opvr.compute_summary_stats()
                    else:
                        opvr.compute_chrom_gene_level_stats(write_summary_pkl = True)
                    print('summary stats were computed')
                    print('Moving input file...')
                    os.rename(input_file, os.path.join(opv.output_dir, 'input_vcf.vcf'))
                    print('Creating folder for downloads...')
                    zipf = zipfile.ZipFile(os.path.join(vcf.results_dir, 'OpenVar_output.zip'), 'w', zipfile.ZIP_DEFLATED)
                    zipdir(opvr.output_dir, zipf)
                    zipf.close()
                    print('Output zipped. Analysis completed!')
        print('Sending email...')
        subject = "Your OpenVar results"
        content = 'Thank you for using OpenVar! Your results are available at this address: www.openprot.org/openvar/' + guid
        sent = send_email(email, subject, mg_domain, mg_key, plain = content)
        print(f"{sent}")
        print('Done!')


    except:
        traceback.print_exc()
        print('Writing error file')
        error_file = os.path.join(os.path.join(result_path, guid), 'error.txt')
        with open(error_file, 'w') as f:
            f.write("We're sorry, something went wrong... Please try again and contact us should the error persists.")
        print('Moving input file...')
        input_file = os.path.join(upload_path, (guid+'.vcf'))
        os.rename(input_file, os.path.join(opv.output_dir, 'input_vcf.vcf'))

#APP ROUTES
# Home page
@app.route('/openvar/', methods=["GET"])
def home():
    return render_template("OPV_home.html")

# Help page
@app.route('/openvar/help')
def help():
    return render_template("OPV_help.html")

# Submit page
@app.route('/openvar/submit', methods=["GET"])
def submit():
    form=CombinedForm()
    form.user_input.genome.choices = [("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19"), ("b37", "GRCH37 / b37")]
    return render_template("OPV_submit.html", form=form)

# Route for user input form submission
@app.route('/openvar/opv_submit', methods=['POST'])
def process_userinput():
    form = CombinedForm(request.form)
    if form.user_input.validate(form.user_input):
        guid = form.user_input.guid.data
        link = '/openvar/' + guid
        email = form.user_input.email.data
        species = form.user_input.species.data
        study_name = form.user_input.study_name.data
        genome_version = form.user_input.genome.data
        annotation = form.user_input.build.data
        
        run_openvar.send(guid, study_name, species, genome_version, annotation, app.config['UPLOAD_PATH'], app.config['RESULTS_PATH'], email, app.config['MG_DOMAIN'], app.config['MG_KEY'])

        return jsonify({'outcome': 'success', 'guid': guid, 'link': link, 'email': email, 'study_name': study_name})
    else:
        return jsonify({'outcome': 'error', 'data': form.errors})

# Results page
@app.route('/openvar/<guid>')
def get_results(guid):
    return render_template("OPV_results.html")

# Results as Json
@app.route('/openvar/<guid>/json')
def get_results_json(guid):
    input_file = os.path.join(app.config['UPLOAD_PATH'], (guid + '.vcf'))
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    output_dir = os.path.join(results_dir, 'output')
    summary_path = os.path.join(output_dir, 'summary.pkl')
    if os.path.exists(summary_path):
        summary = pickle.load(open(summary_path, 'rb'))
        study_name = summary['study_name']
        general_stats = summary['Counts summary']
        chroms = {('Chrom. ' + str(chrom[0])): chrom[1] for chrom in summary['Chromosome Level']}
        if summary['Gene Level'] == []:
            gene_allnulls = 'True'
            top100genes = {}
            top10genes = {}
        else:
            gene_allnulls = 'False'
            top100genes = {gene[0]: gene[1] for gene in summary['Gene Level'][:100]}
            top10genes = {gene[0]: gene[1] for gene in summary['Gene Level'][:10]}
        levels = {"Low":1, "Medium":2, "High":3}
        prot_stats = dict()
        count_graph = dict()
        prot_counts = dict()
        if len(general_stats.keys()) == 3:
            prot_allnulls = hotspots_allnulls = gene_allnulls
            hotspots_top10 = {}
            hotspots_top100 = {}
            altorf_counts = {}
            colors = {}
            mean_impact_per_bin = {}
        else:
            if (len(summary['Protein Level']['Impact Counts']) == 0) and (len(summary['Protein Level']['Fold Change']) == 0) and (len(summary['Protein Level']['Impact Annotation']) == 0):
                prot_allnulls = 'True'
            else:
                prot_allnulls = 'False'
                for key in summary['Protein Level']:
                    if key == 'Impact Counts':
                        count_graph['Alternative protein'] = {n: summary['Protein Level'][key][levels[n]]['alt'] for n in levels.keys()}
                        count_graph['Reference protein'] = {n: summary['Protein Level'][key][levels[n]]['ref'] for n in levels.keys()}
                    elif key == 'Fold Change':
                        prot_counts['Fold Change'] = {n: summary['Protein Level'][key][levels[n]] for n in levels.keys()}
                    elif key == 'Impact Annotation':
                        prot_counts['Classic annotation'] = {n: summary['Protein Level'][key]['ref_all'][levels[n]] for n in levels.keys()}
                        prot_counts['Deep annotation'] = {n: summary['Protein Level'][key]['max_all'][levels[n]] for n in levels.keys()}
                    else:
                        prot_stats[key] = summary['Protein Level'][key]
            if 'All nulls' in summary['Mutational hotspots on altORFs'].keys():
                hotspots_allnulls = 'True'
                hotspots_top10 = {}
                hotspots_top100 = {}
                colors = {}
                altorf_counts = {}
                mean_impact_per_bin = {}
            else:
                hotspots_allnulls = 'False'
                hotspots = dict(zip(list(summary['Mutational hotspots on altORFs'].keys()), [[summary['Mutational hotspots on altORFs'][x]['total_portion_gene'], summary['Mutational hotspots on altORFs'][x]['cnt_snps'], summary['Mutational hotspots on altORFs'][x]['score'], summary['Mutational hotspots on altORFs'][x]['mean_impacts']] for x in list(summary['Mutational hotspots on altORFs'].keys())]))
                sorted_hotspots = {k: v for k, v in sorted(hotspots.items(), key = lambda alt: (alt[1][0], alt[1][2]), reverse=True)}
                hotspots_top10 = dict(zip(list(sorted_hotspots.keys())[:10], list(sorted_hotspots.values())[:10]))
                hotspots_top100 = dict(zip(list(sorted_hotspots.keys())[:100], list(sorted_hotspots.values())[:100]))
                bins = [(0. + (n - 1) * (1. / 30), 0. + n * (1. / 30)) for n in list(range(1, 31))]
                bin_labels = [' - '.join(['{:.2f}'.format(round(x, 2)) for x in left_right]) for left_right in bins]
                altorfs_per_bin = {cat: {n: [] for n in bin_labels} for cat in ['one_snp', 'one_ten', 'over_ten']}
                for gene_alt in summary['Mutational hotspots on altORFs']:
                    for left, right, label in zip([x[0] for x in bins], [x[1] for x in bins], bin_labels):
                        freq = summary['Mutational hotspots on altORFs'][gene_alt]['total_portion_gene']
                        snps = summary['Mutational hotspots on altORFs'][gene_alt]['cnt_snps']
                        mean_impact = summary['Mutational hotspots on altORFs'][gene_alt]['mean_impacts']
                        if (freq > left) and (freq <= right):
                            if snps == 1:
                                altorfs_per_bin['one_snp'][label].append(mean_impact)
                            elif snps < 10:
                                altorfs_per_bin['one_ten'][label].append(mean_impact)
                            else:
                                altorfs_per_bin['over_ten'][label].append(mean_impact)
                altorf_counts = {cat: {n: len(altorfs_per_bin[cat][n]) for n in bin_labels} for cat in ['one_snp', 'one_ten', 'over_ten']}
                colors = ['#f3a6fc', '#cf5fe3', '#7b198c']
                mean_impact_per_bin = {cat: {n: np.mean(altorfs_per_bin[cat][n]) if len(altorfs_per_bin[cat][n]) != 0 else 0. for n in bin_labels} for cat in ['one_snp', 'one_ten', 'over_ten']}

        return jsonify({'outcome': 'success',
            'study_name': study_name,
            'general_stats': general_stats, 
            'chromosomes': chroms, 
            'gene_allnulls': gene_allnulls, 'top10_genes': top10genes, 'top100_genes': top100genes, 
            'prot_allnulls': prot_allnulls, 'prot_stats': prot_stats, 'prot_counts': prot_counts, 'graph_counts': count_graph,
            'hotspots_allnulls': hotspots_allnulls, 'hotspots_top10': hotspots_top10, 'hotspots_top100': hotspots_top100, 
            'hotspot_graph': altorf_counts, 'graph_color': colors, 'mean_impact_per_bin': mean_impact_per_bin})


    elif os.path.exists(os.path.join(results_dir, 'error.txt')):
        with open(os.path.join(results_dir, 'error.txt'), 'r') as error:
            message = error.readline()
            return jsonify({'outcome': 'error', 'message': message, 'tag': 'failed'})
    else:
        if os.path.exists(results_dir):
            message = 'Your analysis is running. Please check again later.'
            return jsonify({'outcome': 'error', 'message': message, 'tag': 'running'})
        elif os.path.exists(input_file):
            message = 'Your analysis has been added to the queue. Please check again later.'
            return jsonify({'outcome': 'error', 'message': message, 'tag': 'running'})
        else:
            message = 'Your files were removed from our server 10 days after completion of the analysis.'
            return jsonify({'outcome': 'error', 'message': message, 'tag': 'deleted'})

# Routes for downloads
@app.route('/openvar/<guid>/download_all', methods = ['GET'])
def download_all(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    return send_from_directory(results_dir, 'OpenVar_output.zip', as_attachment = True)

@app.route('/openvar/<guid>/download_annvcf', methods=['GET'])
def download_annvcf(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    output_dir = os.path.join(results_dir, 'output')
    filename = guid + '.ann.vcf'
    return send_from_directory(output_dir, filename, as_attachment = True)

@app.route('/openvar/<guid>/download_tsv', methods=['GET'])
def download_tsv(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    output_dir = os.path.join(results_dir, 'output')
    filename = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f)) and '_max_impact.tsv' in f][0]
    return send_from_directory(output_dir, filename, as_attachment = True)

# Routes for display all
@app.route('/openvar/<guid>/all_genes', methods = ['GET'])
def get_all_genes(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    output_dir = os.path.join(results_dir, 'output')
    summary_path = os.path.join(output_dir, 'summary.pkl')
    if os.path.exists(summary_path):
        summary = pickle.load(open(summary_path, 'rb'))
        all_genes = {k[0]: k[1] for k in summary['Gene Level']}
        return render_template("all_genes_stats.html",  data = all_genes)
    else:
        return "Error: directory not found."

@app.route('/openvar/<guid>/hotspots_all_genes', methods = ['GET'])
def get_all_hotspots(guid):
    results_dir = os.path.join(app.config['RESULTS_PATH'], guid)
    output_dir = os.path.join(results_dir, 'output')
    summary_path = os.path.join(output_dir, 'summary.pkl')
    if os.path.exists(summary_path):
        summary = pickle.load(open(summary_path, 'rb'))
        hotspots = dict(zip(list(summary['Mutational hotspots on altORFs'].keys()), [[summary['Mutational hotspots on altORFs'][x]['ratio_higher_alt'], summary['Mutational hotspots on altORFs'][x]['cnt_alt_snps'], summary['Mutational hotspots on altORFs'][x]['alts'], summary['Mutational hotspots on altORFs'][x]['ave_impact']] for x in list(summary['Mutational hotspots on altORFs'].keys())]))
        sorted_hotspots = {k: v for k, v in sorted(hotspots.items() , key = lambda gene: (gene[1][0], gene[1][3], gene[1][1], -len(gene[1][2])), reverse=True)}
        return render_template("hotspots_all_genes.html", data = sorted_hotspots)
    else:
        return 'Error: directory not found.'

# Route for upload processing
@app.route('/openvar/upload_file', methods=['POST'])
def upload():
    upload = request.files['file']
    if upload:
        submitted_filename = secure_filename(upload.filename)
        if submitted_filename == '':
            return jsonify({'outcome': 'error', 'error': 'No file selected. Please select a file to upload.'})
        elif submitted_filename[-4:] not in app.config['UPLOAD_EXTENSIONS']:
            return jsonify({'outcome': 'error', 'error': 'Only .vcf, .tsv, .txt and .csv formats are accepted.'})
        elif len([name for name in os.listdir(app.config['UPLOAD_PATH']) if os.path.isfile(os.path.join(app.config['UPLOAD_PATH'], name))]) > 50:
            return jsonify({'outcome': 'error', 'error': "We're sorry but we are experiencing a high demand at the moment. Try again later, but if this message persists, please contact us."})
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
@app.route('/openvar/genome/<species>')
def genome(species):
    genomes = {"human": [("hg38", "GRCh38 / hg38"), ("hg19", "GRCh37 / hg19"), ("b37", "GRCH37 / b37")], "mouse": [("mm39", "GRCm39 / mm39"), ("mm10", "GRCm38 / mm10")], 
            "rat": [("rn7", "RGSC7.0 / rn7"), ("rn6", "RGSC6.0 / rn6")], "fruit fly": [("dm6", "BDGP R6 / dm6"), ("dm3", "BDGP R5 / dm3")]}
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
    port = int(os.getenv("PORT", 5000))
    app.run(host = '0.0.0.0', debug=True, port=port)
