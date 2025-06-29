from flask import Flask, render_template, request, send_file
import os
import uuid
from pydub import AudioSegment
import subprocess

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "processed_audio_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def ensure_stereo_wav(path):
    """Ensure audio file is in stereo."""
    audio = AudioSegment.from_file(path)
    if audio.channels == 1:
        audio = audio.set_channels(2)
        audio.export(path, format="wav")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    audio = request.files.get("audio")
    if not audio:
        return "No file uploaded", 400

    uid = uuid.uuid4().hex
    output_dir = os.path.join(UPLOAD_DIR, f"audio_{uid}")
    os.makedirs(output_dir, exist_ok=True)

    input_filename = f"input_{uid}.wav"
    input_path = os.path.join(output_dir, input_filename)
    audio.save(input_path)
    ensure_stereo_wav(input_path)

    # Temporary Demucs output location (inside same folder)
    demucs_temp_dir = os.path.join(output_dir, "demucs_temp")
    os.makedirs(demucs_temp_dir, exist_ok=True)

    # Run Demucs CLI
    subprocess.run([
        "demucs",
        "--two-stems", "vocals",
        "-o", demucs_temp_dir,
        input_path
    ], check=True)

    # Find and move output files up
    demucs_output = os.path.join(demucs_temp_dir, "htdemucs", input_filename[:-4])  # Remove .wav
    vocals_src = os.path.join(demucs_output, "vocals.wav")
    instrumental_src = os.path.join(demucs_output, "no_vocals.wav")

    vocals_dst = os.path.join(output_dir, "vocals.wav")
    instrumental_dst = os.path.join(output_dir, "instrumental.wav")

    if not os.path.exists(vocals_src) or not os.path.exists(instrumental_src):
        return "Separation failed", 500

    os.rename(vocals_src, vocals_dst)
    os.rename(instrumental_src, instrumental_dst)

    # Clean up Demucs subfolders
    import shutil
    shutil.rmtree(demucs_temp_dir, ignore_errors=True)

    return render_template("result.html", uid=uid)

@app.route("/download/<uid>/<filetype>")
def download_file(uid, filetype):
    audio_dir = os.path.join(UPLOAD_DIR, f"audio_{uid}")
    if filetype == "vocals":
        file_path = os.path.join(audio_dir, "vocals.wav")
        download_name = "vocals.wav"
    elif filetype == "instrumental":
        file_path = os.path.join(audio_dir, "instrumental.wav")
        download_name = "instrumental.wav"
    elif filetype == "input":
        file_path = os.path.join(audio_dir, f"input_{uid}.wav")
        download_name = "original.wav"
    else:
        return "Invalid file type", 400

    if not os.path.exists(file_path):
        return "File not found", 404

    return send_file(file_path, as_attachment=True, download_name=download_name, mimetype="audio/wav")

if __name__ == "__main__":
    app.run(debug=True)