from flask import Flask , render_template , redirect, url_for, request, session , flash
import sqlite3

import time
from requests.exceptions import HTTPError

retry_attempts = 3
retry_wait_time = 5

from googlesearch import search
import PyPDF2
import os
from werkzeug.utils import secure_filename

import re
import math

import textract
from nltk.tokenize import word_tokenize
from gensim.summarization import summarize
from gensim.similarities import Similarity
from gensim import corpora, similarities
from PIL import Image
import pytesseract
import nltk

nltk.download('punkt')

q = ""

path = os.getcwd()
UPLOAD_FOLDER = os.path.join(path, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

app = Flask(__name__)


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.add_url_rule(
    "/uploads/<name>", endpoint="download_file", build_only=True
)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000

app.secret_key = 'key'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

create_tables()


@app.route('/')
def home():
    if 'email' in session:
        email = session['email']
        return redirect(url_for('dashboard', email=email))
    return render_template('intro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Perform login validation here
        email = request.form['email']
        password = request.form['password']

        # Check if the user exists in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

        if user and user['password'] == password:
            # If user exists and password is correct, redirect to the dashboard
            session['email'] = email
            # name = request.args.get('name')
            return redirect(url_for('dashboard', email=email))
        else:
            # If user does not exist or password is incorrect, show error message
            error = 'Invalid credentials. Please try again.'
            return render_template('login.html', error=error)

        # If login is successful, redirect to a different page
        # return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    
    if request.method == 'POST':

        # Perform login validation here
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        # Insert the user data into the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT email FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            # Email already exists, display warning message
            error='Email already exists. Please choose a different email or Choose Login'
            return render_template('signup.html', error=error)
        # cursor.close()
        # conn.close()
        # If login is successful, redirect to a different page
        else:
            # Insert the user data into the database
            cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, password))
            conn.commit()
            session['email'] = email
            return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    # conn = get_db_connection()
    # cursor = conn.cursor()
    # cursor.execute('SELECT name FROM users WHERE email = ?', (email,))
    # result = cursor.fetchone()
    # name = result[0]

    if 'email' in session:
        # email = session['email']
        return render_template('dashboard.html')
    else:
        return redirect(url_for('home'))
    

    # return render_template('dashboard.html',name=name)

@app.route('/logout', methods=['POST'])
def logout():
    # Perform logout functionality here
    session.clear()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.close()
    conn.close()
    # For example, you can clear the session or perform any other required tasks
    # Then redirect the user to the home page
    return redirect(url_for('home'))

@app.after_request
def add_cache_control_headers(response):
    if not session.get('logged_in'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

# @app.route('/dashboard/<email>', methods=['GET', 'POST'])
# def tab1(email):
#     return render_template('index.html',email=email)

@app.route('/dashboard', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.form['text'] != '' and request.files['file'].filename == '':
            word = request.form['text']
            masukan = "word"
            with open('word.txt', 'w', encoding='utf-8') as f:
                f.write(word)
            return redirect(url_for('plagiarism', name=masukan) + "#hasil")
        elif request.files['file'].filename != '' and request.form['text'] == '':
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return redirect(url_for('plagiarism', name=filename) + "#hasil")
        else:
            flash('Please fill the form')
            return redirect(request.url)
    return render_template("dashboard.html")


@app.route('/plagiarism/<name>', methods=['GET', 'POST'])
def plagiarism(name):

    retry_attempts = 3
    retry_wait_time = 5

    domain = "co.id"
    link_output = []
    hasil_plagiarism = []
    hasil_link = []
    hasil_persen = 0
    inputan_mentah = ""
    inputan = []
    filename = ""
    text = ""
    hasil_plagiarism_final = []
    hasil_link_final = []
    link_blocked = ["id.linkedin.com", "linkedin.com", "youtube.com", "instagram.com", "facebook.com", "tokopedia.com",
                    "twitter.com", "reddit.com", "bukalapak.com", "shopee.com", "blibli.com"]
    if request.method == 'POST':
        if request.form['text'] != '' and request.files['file'].filename == '':
            word = request.form['text']
            filename += "word"
            with open('word.txt', 'w', encoding='utf-8') as f:
                f.write(word)
        elif request.files['file'].filename != '' and request.form['text'] == '':
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                pdfFileObj = open('uploads/{}'.format(filename), 'rb')
                pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
                num_pages = pdfReader.numPages
                count = 0
                while count < num_pages:
                    pageObj = pdfReader.getPage(count)
                    count += 1
                    text += pageObj.extractText()
        else:
            flash('Please fill the form')
            return redirect(request.url)

        if filename == "word":
            if request.method == 'POST':
                inputan_mentah += request.form['text']
            else:
                f = open("word.txt", "r")
                inputan_mentah += f.read()
            inputan += inputan_mentah.replace("\n", " ").split(". ")
            for i in range(len(inputan)):
                query = '"' + inputan[i].strip().replace(".", "").replace('"', "'") + '"'
                for j in range(len(list(search(query, tld=domain, num=10, stop=10, pause=2)))):
                    if i != j:
                        continue
                    hasil_plagiarism.append(inputan[i])
                    hasil_link.append(list(search(query, tld=domain, num=10, stop=10, pause=2))[j])
            for i in range(len(hasil_plagiarism)):
                for j in range(len(hasil_link)):
                    if i != j:
                        continue
                    while True:
                        for k in range(len(link_blocked)):
                            if link_blocked[k] in hasil_link[j]:
                                break
                        else:
                            hasil_plagiarism_final.append(hasil_plagiarism[i])
                            hasil_link_final.append(hasil_link[j])
                            break
                        break
            count = len(inputan)
            count_hasil = len(hasil_link_final)
            hasil_persen += (count_hasil / count) * 100
            for i in range(len(hasil_link_final)):
                link_output.append(hasil_link_final[i])
        else:
            inputan += text.replace("\n", " ").split(". ")
            for i in range(len(inputan)):
                query = '"' + inputan[i].strip().replace(".", "").replace('"', "'") + '"'
                for j in range(len(list(search(query, tld=domain, num=10, stop=10, pause=2)))):
                    if i != j:
                        continue
                    hasil_plagiarism.append(inputan[i])
                    hasil_link.append(list(search(query, tld=domain, num=10, stop=10, pause=2))[j])
            for i in range(len(hasil_plagiarism)):
                for j in range(len(hasil_link)):
                    if i != j:
                        continue
                    while True:
                        for k in range(len(link_blocked)):
                            if link_blocked[k] in hasil_link[j]:
                                break
                        else:
                            hasil_plagiarism_final.append(hasil_plagiarism[i])
                            hasil_link_final.append(hasil_link[j])
                            break
                        break
            count = len(inputan)
            count_hasil = len(hasil_link_final)
            hasil_persen += (count_hasil / count) * 100
            for i in range(len(hasil_link_final)):
                link_output.append(hasil_link_final[i])
    else:
        if name == "word":
            if request.method == 'POST':
                inputan_mentah += request.form['text']
            else:
                f = open("word.txt", "r")
                inputan_mentah += f.read()
            inputan += inputan_mentah.replace("\n", " ").split(". ")
            for i in range(len(inputan)):
                query = '"' + inputan[i].strip().replace(".", "").replace('"', "'") + '"'
                for j in range(len(list(search(query, tld=domain, num=10, stop=10, pause=2)))):
                    if i != j:
                        continue
                    hasil_plagiarism.append(inputan[i])
                    hasil_link.append(list(search(query, tld=domain, num=10, stop=10, pause=2))[j])
            for i in range(len(hasil_plagiarism)):
                for j in range(len(hasil_link)):
                    if i != j:
                        continue
                    while True:
                        for k in range(len(link_blocked)):
                            if link_blocked[k] in hasil_link[j]:
                                break
                        else:
                            hasil_plagiarism_final.append(hasil_plagiarism[i])
                            hasil_link_final.append(hasil_link[j])
                            break
                        break
            count = len(inputan)
            count_hasil = len(hasil_link_final)
            hasil_persen += (count_hasil / count) * 100
            for i in range(len(hasil_link_final)):
                link_output.append(hasil_link_final[i])
        else:
            pdfFileObj = open('uploads/{}'.format(name), 'rb')
            pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
            num_pages = pdfReader.numPages
            count = 0
            text = ""
            while count < num_pages:
                pageObj = pdfReader.getPage(count)
                count += 1
                text += pageObj.extractText()
            inputan += text.replace("\n", " ").split(". ")
            # for i in range(len(inputan)):
            #     query = '"' + inputan[i].strip().replace(".", "").replace('"', "'") + '"'
            #     for j in range(len(list(search(query, tld=domain, num=10, stop=10, pause=2)))):
            #         if i != j:
            #             continue
            #         hasil_plagiarism.append(inputan[i])
            #         hasil_link.append(list(search(query, tld=domain, num=10, stop=10, pause=2))[j])

            for i in range(len(inputan)):
                query = '"' + inputan[i].strip().replace(".", "").replace('"', "'") + '"'
                for j in range(len(list(search(query, tld=domain, num=10, stop=10, pause=2)))):
                    if i != j:
                        continue
        
                    for attempt in range(retry_attempts):
                        try:
                            hasil_plagiarism.append(inputan[i])
                            hasil_link.append(list(search(query, tld=domain, num=10, stop=10, pause=2))[j])
                            break  # Successful request, break out of the retry loop
            
                        except HTTPError as e:
                            if e.response.status_code == 429:  # Too Many Requests error
                                print(f"Rate limit exceeded. Retrying in {retry_wait_time} seconds...")
                                time.sleep(retry_wait_time)
                                retry_wait_time *= 2  # Exponential backoff
                            else:
                                raise  # Re-raise the exception if it's not a rate limit error
                    else:
                        print(f"Max retry attempts reached for query: {query}. Skipping...")


            for i in range(len(hasil_plagiarism)):
                for j in range(len(hasil_link)):
                    if i != j:
                        continue
                    while True:
                        for k in range(len(link_blocked)):
                            if link_blocked[k] in hasil_link[j]:
                                break
                        else:
                            hasil_plagiarism_final.append(hasil_plagiarism[i])
                            hasil_link_final.append(hasil_link[j])
                            break
                        break
            count = len(inputan)
            count_hasil = len(hasil_link_final)
            hasil_persen += (count_hasil / count) * 100
            for i in range(len(hasil_link_final)):
                link_output.append(hasil_link_final[i])
    return render_template("dashboard.html", hasil_persen=hasil_persen, data=inputan, hasil_plagiarism=hasil_plagiarism_final,
                           link_output=link_output, hasil_link=hasil_link_final)

# @app.route('/tab2')
# def tab2():
#     return render_template('index2.html')

@app.route("/dashboard/PlagiarismChecker")
def loadPage():
	return render_template('index2.html', query="")
@app.route("/dashboard/PlagiarismChecker", methods=['GET', 'POST'])
def similarity():
    try:
        universalSetOfUniqueWords = []
        matchPercentage = 0

        if request.method == 'POST':
            inputQuery = request.form['query']
            lowercaseQuery = inputQuery.lower()

            queryWordList = re.sub("[^\w]", " ", lowercaseQuery).split()
            for word in queryWordList:
                if word not in universalSetOfUniqueWords:
                    universalSetOfUniqueWords.append(word)

            fd = open("database1.txt", "r")
            database1 = fd.read().lower()

            databaseWordList = re.sub("[^\w]", " ", database1).split()
            for word in databaseWordList:
                if word not in universalSetOfUniqueWords:
                    universalSetOfUniqueWords.append(word)

            queryTF = []
            databaseTF = []

            for word in universalSetOfUniqueWords:
                queryTfCounter = 0
                databaseTfCounter = 0

                for word2 in queryWordList:
                    if word == word2:
                        queryTfCounter += 1
                queryTF.append(queryTfCounter)

                for word2 in databaseWordList:
                    if word == word2:
                        databaseTfCounter += 1
                databaseTF.append(databaseTfCounter)

            dotProduct = 0
            for i in range(len(queryTF)):
                dotProduct += queryTF[i] * databaseTF[i]

            queryVectorMagnitude = 0
            for i in range(len(queryTF)):
                queryVectorMagnitude += queryTF[i] ** 2
            queryVectorMagnitude = math.sqrt(queryVectorMagnitude)

            databaseVectorMagnitude = 0
            for i in range(len(databaseTF)):
                databaseVectorMagnitude += databaseTF[i] ** 2
            databaseVectorMagnitude = math.sqrt(databaseVectorMagnitude)

            matchPercentage = (float)(dotProduct / (queryVectorMagnitude * databaseVectorMagnitude)) * 100

            output = "Input query text matches %0.02f%% with the database." % matchPercentage

            return render_template('index2.html', query=inputQuery, output=output)
        
        else:
            return render_template('index2.html', query="", output="")
        # return render_template('index2.html', query="", output="")
        
    except Exception as e:
        output = "Please enter valid data"
        return render_template('index2.html', query="", output=output)


@app.route('/dashboard/SimilarityChecker', methods=['GET', 'POST'])
def document():
    similarity_score = ''
    summary1 = ''
    summary2 = ''
    text1 = ''
    text2 = ''
    filename2 = ''

    if request.method == 'POST':
        # Check if files were uploaded
        if 'file1' not in request.files or 'file2' not in request.files:
            return "Please upload both File 1 and File 2."

        file1 = request.files['file1']
        file2 = request.files['file2']

        # Check if files have valid extensions
        if file1 and allowed_file(file1.filename) and file2 and allowed_file(file2.filename):
            # Save the uploaded files to the upload folder
            filename1 = secure_filename(file1.filename)
            file1_path = os.path.join(app.config['UPLOAD_FOLDER'], filename1)
            file1.save(file1_path)

            filename2 = secure_filename(file2.filename)
            file2_path = os.path.join(app.config['UPLOAD_FOLDER'], filename2)
            file2.save(file2_path)

            # Extract text from the uploaded files
            text1 = extract_text(file1_path)
            text2 = extract_text(file2_path)

            # Calculate plagiarism percentage
            similarity_score = calculate_similarity(text1, text2)

            # Generate summaries
            summary1 = generate_summary(text1)
            summary2 = generate_summary(text2)

    return render_template('index3.html', similarity_score=similarity_score, summary1=summary1, summary2=summary2, text1=text1, text2=text2)


# Function to check if the uploaded file has a valid extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Function to extract text from files
def extract_text(file_path):
    # Extract text from PDF files
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfFileReader(pdf_file)
            text = ''
            for page_num in range(pdf_reader.numPages):
                page = pdf_reader.getPage(page_num)
                text += page.extractText()
        return text

    # Extract text from document files
    elif file_path.endswith(('.doc', '.docx', '.txt')):
        text = textract.process(file_path).decode('utf-8')
        return text

    else:
        return ''


# Function to calculate similarity between two texts
def calculate_similarity(text1, text2):
    documents = [text1.split(), text2.split()]
    dictionary = corpora.Dictionary(documents)
    corpus = [dictionary.doc2bow(doc) for doc in documents]
    similarity_matrix = similarities.Similarity('', corpus, num_features=len(dictionary))
    similarity = similarity_matrix[corpus[0]][1] * 100  # Get similarity between first and second document
    return similarity


# Function to generate summary of a text
def generate_summary(text):
    return summarize(text)

if __name__ == '__main__':
    app.run(debug=True)

