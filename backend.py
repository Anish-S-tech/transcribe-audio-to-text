# Full Flask App with MongoDB for Audio-to-Text

import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
from pydub import AudioSegment
import speech_recognition as sr
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
from dotenv import load_dotenv


# Flask Setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = 'uploads/'

load_dotenv()
# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MongoDB Setup
client = MongoClient(os.getenv('MONGO_URI'))  
db = client['audio_app']
users_col = db['users']
transcripts_col = db['transcripts']
fs = GridFS(db)

# Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data['email']

@login_manager.user_loader
def load_user(user_id):
    user = users_col.find_one({'_id': ObjectId(user_id)})
    return User(user) if user else None

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        if users_col.find_one({'email': email}):
            return 'Email already exists'
        user_id = users_col.insert_one({'email': email, 'password': password}).inserted_id
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = users_col.find_one({'email': request.form['email']})
        if user and bcrypt.check_password_hash(user['password'], request.form['password']):
            login_user(User(user))
            return redirect(url_for('dashboard'))
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = ObjectId(session['_user_id'])
    records = list(transcripts_col.find({'user_id': user_id}))
    return render_template('dashboard.html', history=records)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)

        # Convert MP3 to WAV if needed
        if ext == '.mp3':
            sound = AudioSegment.from_mp3(temp_path)
            wav_path = temp_path.replace('.mp3', '.wav')
            sound.export(wav_path, format='wav')
        else:
            wav_path = temp_path

        # Transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data)
            except:
                text = '[Unrecognizable]'

        # Save audio to GridFS
        audio_id = fs.put(open(wav_path, 'rb'), filename=filename)

        # Save record
        transcripts_col.insert_one({
            'user_id': ObjectId(session['_user_id']),
            'filename': filename,
            'transcription': text,
            'audio_id': audio_id
        })

        # Cleanup
        os.remove(temp_path)
        if wav_path != temp_path:
            os.remove(wav_path)

        return render_template('result.html', text=text)

    return render_template('upload.html')

@app.route('/download/<audio_id>')
@login_required
def download(audio_id):
    file = fs.get(ObjectId(audio_id))
    return send_file(file, download_name=file.filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
