from elasticsearch import Elasticsearch
import json, os
import PyPDF2
from flask import Flask, request, render_template, flash, send_file
from docx import *

from logstash_async.handler import AsynchronousLogstashHandler
from logstash_async.formatter import FlaskLogstashFormatter


##Connect to ElasticSearch
def connect_elasticsearch():
    es = None
    es = Elasticsearch([{'host': 'localhost', 'port': 9200}], http_auth=('elastic', 'changeme'))
    if es.ping():
        app.logger.info("Connection Successful")
        print('Connection Successful')
    else:
        app.logger.info("Error: It could not connect")
        print('Error: it could not connect!')
    return es


# Creation of the index
def create_index(es):
    es.indices.create(index='cvs', ignore=400)
    app.logger.info("Indice cvs created")
    return es


# Function that populates the index with the user's uploads
def populate_index(es, data):
    es.index(index='cvs', ignore=400, doc_type="cv", body=data)


# Web# Getting CV from user
# and downloading the cv into an internal folder and indexing the information related to the candidate
# and the content of the CV
def GetCV(name, lname, email, number, filen):
    filename = "uploads/" + filen
    file_ext = os.path.splitext(filename)[1]
    if file_ext == '.pdf':
        file = open('download/'+filename, 'rb')
        read_pdf = PyPDF2.PdfFileReader(file)
        number_of_pages = read_pdf.getNumPages()
        i = 0
        page_content = ""
        while i < number_of_pages:
            page = read_pdf.getPage(i)
            page_content += page.extractText()
            i += 1
        cv = {"FirstName": name, "LastName": lname, "email": email, "number": number, "cvpath": filename,
          "Summary": page_content}
        cvjson = json.dumps(cv)
    else:
        file = open('download/'+filename, 'rb')
        document = Document(file)
        page_content = ""
        for para in document.paragraphs:
            page_content += para.text
        cv = {"FirstName": name, "LastName": lname, "email": email, "number": number, "cvpath": filename,
              "Summary": page_content}
        cvjson = json.dumps(cv)
    return (cvjson)

def main():
    app = Flask(__name__)  # create an app instance
    es = connect_elasticsearch()
    es = create_index(es)
    app.config['UPLOAD_EXTENSIONS'] = ['.pdf', '.doc', '.docx']
    app.config['UPLOAD_PATH'] = 'download/uploads/'
    app.config["SECRET_KEY"] = os.urandom(24)
    ####################################################################################################
    # logstash
    LOGSTASH_HOST = "localhost"
    LOGSTASH_DB_PATH = "flask_logstash.db"
    LOGSTASH_TRANSPORT = "logstash_async.transport.BeatsTransport"
    LOGSTASH_PORT = 5044

    logstash_handler = AsynchronousLogstashHandler(
        LOGSTASH_HOST,
        LOGSTASH_PORT,
        database_path=LOGSTASH_DB_PATH,
        transport=LOGSTASH_TRANSPORT,
    )
    logstash_handler.formatter = FlaskLogstashFormatter(metadata={"beat": "myapp"})
    app.logger.addHandler(logstash_handler)

    #####################################################################################################
    @app.route('/', methods=["GET", "POST"])
    def mainpage():
        app.logger.info("Hello there")
        if request.method == "POST":
            if request.form.get("search"):
                return render_template("search.html")
            if request.form.get("add"):
                    return render_template("index.html")
        return render_template("mainpage.html")


    @app.route('/addcv', methods=["GET", "POST"])
    def addcv():
        if request.method == "POST":
            uploaded_file = request.files['file']
            filename = uploaded_file.filename
            if filename != '':
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in app.config['UPLOAD_EXTENSIONS']:
                    app.logger.info("extension not accepted")
                    flash("extension not accepted.")
                else:
                    uploaded_file.save(os.path.join(app.config['UPLOAD_PATH'], filename))
                    app.logger.info("CV saved successfully")
                    flash("cv saved successfully.")
                    fname = request.form.get("fname")
                    lname = request.form.get("lname")
                    email = request.form.get("email")
                    tel = request.form.get("tel")
                    data = GetCV(fname, lname, email, tel, filename)
                    populate_index(es, data)
        return render_template("index.html")

    @app.route("/download", methods=['Get', 'POST'])
    def downloadfile():
        path="download/"+request.args.get('path')
        return send_file(path, as_attachment=True)

    @app.route("/searchindex", methods=['GET', 'POST'])  # at the end point /
    def getindex():  # call method hello
        if request.method == "POST":
            s = request.form.get("search")
            res = es.search(index="cvs", body={"query": {"match": {"Summary": s}}})
            if res['hits']['total']['value'] != 0:
                return render_template('displaycv.html', res=res)
            else:
                app.logger.info("No cv were found")
                return ("NO CV FOUND CORRESPENDING TO THE SEARCH")
        return render_template("search.html")



    if __name__ == "__main__":
        app.run()  # run the flask app
        app.logger.info("test")
        return 'hello'

app = Flask(__name__)  # create an app instance

main()
