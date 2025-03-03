from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="static")  
CORS(app)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/upload", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", audio_file.filename)
    audio_file.save(audio_path)
    
    text = "test"
    ai_response = "test"
    return jsonify({"text": text, "ai_response": ai_response})

if __name__ == "__main__":
    app.run(debug=True)
