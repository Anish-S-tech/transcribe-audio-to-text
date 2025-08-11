import os
from flask import Flask, render_template, request, redirect, url_for, send_file,session
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
from pydub import AudioSegment
import speech_recognition as sr
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask Setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret')
app.config['UPLOAD_FOLDER'] = 'uploads/'
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
login_manager.login_view = 'login'
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
        users_col.insert_one({'email': email, 'password': password})
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
    records = list(transcripts_col.find({'user_id': ObjectId(current_user.id)}))
    return render_template('dashboard.html', history=records)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if not file:
            return "No file uploaded", 400

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

        # Transcribe in chunks
        recognizer = sr.Recognizer()
        audio = AudioSegment.from_wav(wav_path)
        chunk_length_ms = 30 * 1000  # 30 seconds
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

        full_text = []
        for i, chunk in enumerate(chunks):
            chunk_filename = f"temp_chunk_{i}.wav"
            chunk.export(chunk_filename, format="wav")

            with sr.AudioFile(chunk_filename) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data)
                    full_text.append(text)
                except sr.UnknownValueError:
                    # Skip unrecognizable chunks instead of adding spam
                    pass
                except sr.RequestError:
                    full_text.append("[API Error]")

            os.remove(chunk_filename)

        final_text = " ".join(full_text).strip() if full_text else "[No speech recognized]"

        # Save audio to GridFS
        audio_id = fs.put(open(wav_path, 'rb'), filename=filename)

        # Save record in MongoDB
        transcripts_col.insert_one({
            'user_id': ObjectId(session['_user_id']),
            'filename': filename,
            'transcription': final_text,
            'audio_id': audio_id
        })

        # Cleanup
        os.remove(temp_path)
        if wav_path != temp_path:
            os.remove(wav_path)

        return render_template('result.html', text=final_text)

        return render_template('upload.html')



        # join parts and strip
        text = " ".join(full_parts).strip()
        # === end improved block ===

        # Save to DB
        with open(wav_path, 'rb') as f:
            audio_id = fs.put(f, filename=filename)

        transcripts_col.insert_one({
            'user_id': ObjectId(current_user.id),
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
