from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit
import threading

load_dotenv()

app = Flask(__name__, static_folder="static")  
CORS(app)
socketio = SocketIO(app)

@app.route("/")
def index():
    return send_from_directory("static", "index06.html")

@app.route("/upload", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", audio_file.filename)
    audio_file.save(audio_path)

    # 音声認識
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = r.record(source)
        text = r.recognize_google(audio, language="ja-JP")
        if __debug__: # デバッグモードの場合
            print(text)

    # 音声認識の結果を最初に返す
    response = jsonify({"text": text})
    
    # 別スレッドでAIの応答を取得
    threading.Thread(target=get_ai_response, args=(text,)).start()
    
    return response

def get_ai_response(text):
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": text},
        ]
    )
    ai_response = completion.choices[0].message.content
    # WebSocketを通じてクライアントに通知
    socketio.emit('ai_response', {'ai_response': ai_response})

if __name__ == "__main__":
    socketio.run(app, debug=True)
