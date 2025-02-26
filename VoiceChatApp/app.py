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
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language="ja-JP")
        except sr.UnknownValueError:
            return jsonify({"text": "認識できませんでした。", "ai_response": ""}), 400
        except sr.RequestError:
            return jsonify({"text": "Speech Recognition API error", "ai_response": ""}), 500

    # OpenAI APIでテキストを処理
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたは親切なアシスタントです。"},
            {"role": "user", "content": text}
        ]
    )

    ai_response = response["choices"][0]["message"]["content"]
    return jsonify({"text": text, "ai_response": ai_response})

if __name__ == "__main__":
    app.run(debug=True)
