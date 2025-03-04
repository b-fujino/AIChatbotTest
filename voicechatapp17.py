

from flask import Flask, request, Response, jsonify, send_from_directory, send_file, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv
import requests
import time
import logging
import json
from pydub import AudioSegment
from io import BytesIO
import base64


#　環境変数の読み込み
load_dotenv()

# VoiceVox APIのエンドポイント
VOICEVOX_API_URL = "http://localhost:50021"


# Flaskアプリケーションの作成
app = Flask(__name__, static_folder="static")  

# CORSの設定
CORS(app)

# Socket.IOの設定
socketio = SocketIO(app)

# 会話ログを保持する変数
messages = [
    {"role": "system", "content": "You are a helpful assistant."}
]

# 区切り文字の設定．AI出力をストリームで受け取るときに句切りをどの文字で行なうかの指定
# この文字が来たら，その前までを一つの句として扱う
SegmentingChars=",，、。．.:;？?！!\n"

#loggingの設定
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filename="app.log",
    encoding="utf-8"
)

#--------------------------------------------------
# Flaskのエンドポイントの作成
#--------------------------------------------------

# ルートパスへのリクエストを処理する
@app.route("/")
def index():
    logging.info("index.html を返します。")
    return send_from_directory("static", "index17.html")

# VoiceVoxのSpeakerIDリストを取得するエンドポイント
@app.route("/speaker_ids")
def get_speaker_ids():
    url = f"{VOICEVOX_API_URL}/speakers"  # VOICEVOX APIのエンドポイント
    try:
        response = requests.get(url)
    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify([])

    voicevox_speakers = []
    if response.status_code == 200:
        speakers = response.json()
        for speaker in speakers:
            name = speaker['name']
            style_names = [style['name'] for style in speaker['styles']]
            style_ids = [style['id'] for style in speaker['styles']]
            for style_id, style_name in zip(style_ids, style_names):
                voicevox_speakers.append(f"<option value={style_id}>Speaker: {name}, {style_name} </option>")
        logging.info("speaker_ids を取得しました。")
        return jsonify(voicevox_speakers)
    else:
        logging.error(f"Error: {response.status_code}")
        return jsonify([])    

# 音声テストを行うエンドポイント
@app.route("/speaker_test" , methods=["POST"])
def speaker_test():
    TTS = request.form["TTS"]
    speaker = request.form["speakerId"]
    languageCode = request.form["languageCode"]
    JPvoicetype = request.form["JPvoicetype"]
    ENvoicetype = request.form["ENvoicetype"]
    logging.debug(f"speaker_test: TTS={TTS}, speaker={speaker}, languageCode={languageCode}, JPvoicetype={JPvoicetype}, ENvoicetype={ENvoicetype}")

    if TTS == "VoiceVox":
        text = "こんにちは．初めまして．何かお手伝いできることはありますか？"
    elif TTS == "Google":
        # 日本語と英語で分岐
        if languageCode == "ja-JP":
            text = f"こんにちは．初めまして．何かお手伝いできることはありますか？"
        elif languageCode == "en-US":
            text = f"Hello. Nice to meet you. How can I help you?"
        else:
            return jsonify({"error": "Failed to synthesize voice_Test. Input languageCode is irregal"}), 400
        # Google Cloud TTS APIで音声合成
    else:
        return jsonify({"error": "Failed to synthesize voice_Test. Input TTS is irregal"}), 400

    # 音声合成
    mp3_data = synthesize_voice(text, request.form)
    if mp3_data is None: return jsonify({"error": "Failed to synthesize voice"}), 400
    socketio.emit('play_audio', {'audio': mp3_data.getvalue()})
    return jsonify({"info": "Speaker Test Process Succeeded"}), 200


# /upload へのリクエストを処理する
@app.route("/upload", methods=["POST"])
def upload_audio():
    logging.debug("request.form: %s", request.form)
    logging.debug("request.files: %s", request.files)
    # uploads ディレクトリがなければ作成
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    # uploads ディレクトリにファイルがあれば削除
    else:
        for file in os.listdir("uploads"):
            os.remove(os.path.join("uploads", file))

    # 音声ファイルをアップロード
    if "file" not in request.files:
        logging.error("No audio file provided")
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", f"input_{len(messages)}.wav") #Uploadされたファイルを残すならこっちをOn
    audio_file.save(audio_path)

    # 音声認識
    start_time_sr = time.time()
    text = recognize_speech(audio_path, request.form)
    logging.debug(f"UPLOAD: 音声認識にかかった時間: {time.time() - start_time_sr :.2f}秒")
    ## 音声認識の結果をWebSocketを通じてクライアントに通知
    if text:
        socketio.emit("SpeechRecognition",{"text": text})
    else:
        return jsonify({"error": "Failed to recognize speech"}), 400    
    
    # AIの応答を取得
    start_time_ai = time.time()
    ai_response = get_ai_response(text)
    logging.debug(f"UPLOAD: AIの応答にかかった時間: {time.time() - start_time_ai :.2f}秒")
    ## WebSocketを通じてクライアントに通知
    if ai_response:
        socketio.emit('ai_response', {'ai_response': ai_response}) 
    else:
        return jsonify({"error": "Failed to get AI response"}), 400
    
    # AIの応答から音声合成してmp3で返す
    start_time_sv = time.time()
    mp3_data = synthesize_voice(ai_response, request.form)
    logging.debug(f"UPLOAD: 音声合成にかかった時間: {time.time() - start_time_sv :.2f}秒")
    logging.debug(f"UPLOAD: 合計処理時間: {time.time() - start_time_ai :.2f}秒")
    if mp3_data is None: return jsonify({"error": "Failed to synthesize voice"}), 400

    # mp3データをWebSocketを通じてクライアントに通知
    socketio.emit('play_audio', {'audio': mp3_data.getvalue()})

    return jsonify({"info": "Uploard Process Succeeded"}), 200



# streaming処理するエンドポイント
@app.route("/streaming", methods=["POST"])
def streaming():
    # uploads ディレクトリがなければ作成
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    # uploads ディレクトリにファイルがあれば削除
    else:
        for file in os.listdir("uploads"):
            os.remove(os.path.join("uploads", file))

    # 音声ファイルをアップロード
    if "file" not in request.files:
        logging.error("No audio file provided")
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["file"]
    audio_path = os.path.join("uploads", "input.wav") #Uploadされたファイルを残さないならこっちをOn
    audio_file.save(audio_path)

    # 音声認識
    start_time_sr = time.time()
    text = recognize_speech(audio_path, request.form)
    logging.debug(f"STREAMING: 音声認識にかかった時間: {time.time() - start_time_sr :.2f}秒")
    ## 音声認識の結果をWebSocketを通じてクライアントに通知
    if text:
        socketio.emit("SpeechRecognition",{"text": text})
    else:
        return jsonify({"error": "Failed to recognize speech"}), 400    
    

    # AIの応答を句単位でストリームするとともに．句単位で音声合成もしていく
    socketio.emit('ai_stream', {'sentens': "---Start---"}) # 開始を通知
    start_time_stream = time.time()
    for sentence in generate_ai_response(text):
        ## WebSocketを通じてクライアントに通知
        if sentence:
            #　音声合成（mp3出力）
            mp3_data = synthesize_voice(sentence, request.form)
            if mp3_data is None: return jsonify({"error": "Failed to synthesize voice"}), 400
            ## mp3データをWebSocketを通じてクライアントに通知 ここでうまくキューに入れて連続再生させたい
            socketio.emit('ai_stream', {'audio': mp3_data.getvalue(), 'sentens': sentence})
            
            # sentensの区切り文字が読点だったら，0.2秒の無音を入れる
            if sentence[-1] in ",，、":
                silent_audio = AudioSegment.silent(duration=10)
                mp3_data  = BytesIO()
                silent_audio.export(mp3_data , format="mp3")
                mp3_data .seek(0)
            # sentensの区切り文字が読点でなかったら，0.5秒の無音を入れる
            else:
                silent_audio = AudioSegment.silent(duration=500)
                mp3_data  = BytesIO()
                silent_audio.export(mp3_data , format="mp3")
                mp3_data .seek(0)
            # 無音を送信
            socketio.emit('ai_stream', {'audio': mp3_data.getvalue(), 'sentens': "---silent---"})
        else:
            return jsonify({"error": "Failed to get AI response"}), 400
    logging.debug(f"STREAMING: ストリーミング処理にかかった時間: {time.time() - start_time_stream :.2f}秒")
    socketio.emit('ai_stream', {'sentens': "---End---"}) # 終了を通知

    
    return jsonify({"info": "Process Succeeded"}), 200


#--------------------------------------------------
# Flaskの各エンドポイント内の処理関数
#--------------------------------------------------
# 音声認識を行う関数
def recognize_speech(audio_path, form):
    languageCode = form["languageCode"]
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = r.record(source)
        text = r.recognize_google(audio, language=languageCode)
    return text

# OpenAIのAPIを呼び出してAIの応答を取得する関数
def get_ai_response(text):
    client = OpenAI()
    messages.append({"role": "user", "content": text})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    ai_response = completion.choices[0].message.content
    messages.append({"role": "assistant", "content": ai_response})
    logging.info(f"AIの応答: {ai_response}")
    return ai_response

# OpenAIのAPIを呼び出してAIの応答をストリームで生成する関数
def generate_ai_response(text):

    """"
    色々なチェーン処理を書くならここに入れる．
    Claude : https://note.com/noa813/n/n307d62b5820b
    Gemini : https://qiita.com/RyutoYoda/items/a51830dd75a2dac96d72
             https://ai.google.dev/api?hl=ja&lang=python
    """
    client = OpenAI()
    messages.append({"role": "user", "content": text})
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream = True
    )

    sentens = "" # 句を構成するためのバッファ　
    message = "" # プロンプトに含めるためにチャンクを結合させるためのためのバッファ
    for chunk in completion:
        # きちんとしたチャンクが帰ってきているかのチェック
        if "choices" in chunk.to_dict() and len(chunk.choices) > 0: #to_dict：辞書型に変えないと”choices”が見つからないようなので
            content  = chunk.choices[0].delta.content
            if content:
                message += content
                # 1文字ずつ取り出してチェックする
                for i in range(len(content)):
                    char = content[i]
                    sentens += char
                    if char in SegmentingChars: #今見ているのが区切り文字だった場合（読点も区切りに含める）
                        if i < len(content)-1: # i が最後の文字でないなら，次の文字をチェック
                            if content[i+1] not in SegmentingChars: #次の文字が区切り文字でないならyield
                                #logging.debug(f"句: {sentens}")
                                yield sentens
                                sentens = ""
                            else: #もし次の文字が区切り文字なら，現時点の区切り文字はスルー
                                continue
                        else: #iが最後の文字の場合，現時点でyield
                            #logging.debug(f"句: {sentens}")
                            yield sentens
                            sentens = ""
    # 最後の句を返す
    if sentens:
        yield sentens
    
    # message をmessagesに追加
    messages.append({"role": "assistant", "content": message})
    logging.info(f"AIの応答: {message}")

# 各種APIを使って音声合成を行うラッパー関数
def synthesize_voice(text, form):
    # TTSの種類情報を取得
    TTS = form["TTS"]
    speaker = form["speakerId"]
    languageCode = form["languageCode"]
    JPvoicetype = form["JPvoicetype"]
    ENvoicetype = form["ENvoicetype"]
    logging.debug(f"speaker_test: TTS={TTS}, speaker={speaker}, languageCode={languageCode}, JPvoicetype={JPvoicetype}, ENvoicetype={ENvoicetype}")

    #Textに読み上げしない文字が含まれてる場合はその文字をTextから外す
    text = text.replace("#", "") # 見出し文字#を削除
    text = text.replace("**", "") # 協調表示**を削除

    if TTS == "VoiceVox":
        mp3_data = synthesize_voicevox_mp3(text, speaker)
    elif TTS == "Google":
        # 日本語と英語で分岐
        if languageCode == "ja-JP":
            voicetype = JPvoicetype
        elif languageCode == "en-US":
            voicetype = ENvoicetype
        else:# 日本語でも英語でもない場合
            return jsonify({"error": "Failed to synthesize voice_Test. Input languageCode is irregal"}), 400
        # Google Cloud TTS APIで音声合成
        mp3_data = synthesize_voice_google(text,languageCode, voicetype)
    else: # TTSがVoiceVoxでもGoogleでもない場合
        return jsonify({"error": "Failed to synthesize voice_Test. Input TTS is irregal"}), 400
    
    if mp3_data is None: 
        return jsonify({"error": "Failed to synthesize voice"}), 400
    # mp3 データを返す    
    return mp3_data

# VoiceVox APIで音声合成を行う関数 (wav出力)
def synthesize_voicevox(text, speaker):
    # 1. テキストから音声合成のためのクエリを作成
    query_payload = {'text': text, 'speaker': speaker}
    query_response = requests.post(f'{VOICEVOX_API_URL}/audio_query', params=query_payload)

    if query_response.status_code != 200:
        logging.error(f"Error in audio_query: {query_response.text}")
        print(f"Error in audio_query: {query_response.text}")
        return

    query = query_response.json()

    # 2. クエリを元に音声データを生成
    synthesis_payload = {'speaker': speaker}
    synthesis_response = requests.post(f'{VOICEVOX_API_URL}/synthesis', params=synthesis_payload, json=query)

    if synthesis_response.status_code == 200:
        logging.info("音声データを生成しました。")
        return synthesis_response
    else:
        logging.error(f"Error in synthesis: {synthesis_response.text}")
        return None


# voicevox で音声合成を行う関数（mp3出力）
def synthesize_voicevox_mp3(text, speaker):
    # voicecvox apiでwavデータを生成
    synthesis_response = synthesize_voicevox(text, speaker)

    if synthesis_response.status_code == 200:
        logging.info("音声データを生成しました。")
        audio = AudioSegment.from_file(BytesIO(synthesis_response.content), format="wav")
        mp3_data  = BytesIO()
        audio.export(mp3_data , format="mp3")
        mp3_data .seek(0)  
        return mp3_data
    else:
        logging.error(f"Error in synthesis: {synthesis_response.text}")
        return None

# Google Clout TTS APIで音声合成を行う関数
def synthesize_voice_google(text,langcode="ja-JP", voicetype="ja-JP-Wavenet-A"):
    # APIキーの取得
    API_KEY = os.getenv("GOOGLE_TTS_API_KEY")

    # APIエンドポイント
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={API_KEY}"

    # 音声合成のリクエストデータ
    data = {
        "input": {"text": text},
        "voice": {
            "languageCode": langcode,
            "name": voicetype,  
#            "ssmlGender": "MALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3"
        }
    }

    # リクエスト送信
    response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data))

    # 結果を取得
    if response.status_code == 200:
        # Base64エンコードされた音声データをデコード
        audio_content = json.loads(response.text)["audioContent"]
        audio_data = base64.b64decode(audio_content)
        
        # バイナリデータを pydub の AudioSegment に変換
        mp3_data  =BytesIO(audio_data)
        mp3_data .seek(0)  
        return mp3_data
    else:
        logging.error(f"Error in synthesis: {response.text}")
        return None
    
if __name__ == "__main__":
    logging.info("#####アプリケーションを起動します。#####")
    socketio.run(app, debug=True)
