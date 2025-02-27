from flask import Flask, request, jsonify, render_template
import speech_recognition as sr
import openai
import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__, static_folder="static", template_folder="static")

@app.route("/")
def index():
    return render_template("index.html")  # フロントエンドのHTMLを表示

@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["audio"]
    audio_path = os.path.join("uploads", audio_file.filename)
    audio_file.save(audio_path)
    
    text = "test"
    ai_response = "test"
    return jsonify({"text": text, "ai_response": ai_response})

if __name__ == "__main__":
    app.run(debug=True)
