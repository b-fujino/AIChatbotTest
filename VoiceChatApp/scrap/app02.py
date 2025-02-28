
from flask import Flask, request, jsonify, render_template
import os
import subprocess

app = Flask(__name__)

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

# 使い方

if __name__ == "__main__":
    app.run(debug=True)
