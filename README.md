This is a full-stack web application built with Flask (Python) that allows users to upload audio files and convert them to text. Users can register, log in, upload .mp3 or .wav files, and receive transcriptions powered by Google Speech Recognition. Audio files are stored in Google Cloud Storage (GCS), while transcription history is saved per user in Firestore.

Technologies Used:

This project leverages powerful technologies for both backend and cloud services. Flask serves as the core web framework. Firebase Authentication handles user login and registration. GCS securely stores uploaded audio files, and Firestore keeps track of each user's transcription history. The speech_recognition library is used for converting speech to text, and pydub helps convert .mp3 files to .wav format when needed

Features:

1. User authentication via Firebase

2. Upload audio files in .mp3 or .wav format

3. Speech-to-text transcription using Google API

4. Audio file storage in Google Cloud Storage

5. History of past uploads saved in Firestore

6. Clean user dashboard with downloadable audio links
