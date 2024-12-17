from flask import Flask, request, jsonify
import numpy as np
import wave
import os
from scipy.fft import fft, ifft
import logging

app = Flask(__name__)

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Utility Functions
def text_to_binary_with_stop(text):
    binary_data = ''.join(format(ord(char), '08b') for char in text)
    stopper = '10101011'  # New stopper pattern
    logging.debug(f"Binary data for text '{text}': {binary_data}")
    logging.debug(f"Adding stopper: {stopper}")
    return binary_data + stopper


def binary_to_text_with_stop(binary_data):
    stopper = '10101011'
    logging.debug(f"Extracted binary data: {binary_data}")
    if stopper in binary_data:
        # Extract binary up to the stopper
        message_binary = binary_data.split(stopper)[0]
        logging.debug(f"Message binary before stopper: {message_binary}")

        # Convert binary to text
        chars = [chr(int(message_binary[i:i+8], 2)) for i in range(0, len(message_binary), 8)]
        return ''.join(chars)
    else:
        logging.error("Stopper not found in the binary data")
        raise ValueError("Stopper not found in the binary data")

def embed_binary_into_audio(audio_data, binary_data):
    audio_data = np.copy(audio_data)  # Avoid modifying the original audio
    binary_index = 0

    freq_data = fft(audio_data)

    base_index = 100
    delta = 10  # Increased delta for better distinction
    max_bins = len(audio_data) // 2  # Maximum usable bins

    if base_index + len(binary_data) > max_bins:
        raise ValueError("Binary data exceeds the available frequency bins")

    for i in range(base_index, base_index + len(binary_data)):
        bit = int(binary_data[binary_index])
        freq_data[i] += delta if bit == 1 else -delta
        binary_index += 1

    stego_audio = np.real(ifft(freq_data))
    return stego_audio.astype(np.int16)


def extract_binary_from_audio(audio_data):
    freq_data = fft(audio_data)

    base_index = 100
    delta = 100  # Match embedding delta
    threshold = delta / 2
    binary_data = ''

    for i in range(base_index, base_index + 100):  # Adjust based on binary length
        binary_data += '1' if freq_data[i].real > threshold else '0'

    return binary_data

def save_audio(audio_data, filename, params):
    logging.debug(f"Saving audio to file: {filename}")
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setparams(params)
        wav_file.writeframes(audio_data.tobytes())
    logging.debug("Audio file saved successfully")

def load_audio(file):
    logging.debug(f"Loading audio file: {file.filename}")
    with wave.open(file, 'rb') as wav_file:
        params = wav_file.getparams()
        frames = wav_file.readframes(params.nframes)
        audio_data = np.frombuffer(frames, dtype=np.int16)
    
    # Handle stereo audio by selecting one channel
    if params.nchannels == 2:  # Stereo
        audio_data = audio_data[::2]  # Select the left channel
        logging.debug("Stereo audio detected. Using left channel only.")
    
    logging.debug(f"Audio loaded. Params: {params}")
    return audio_data, params


@app.route('/embed', methods=['POST'])
def embed():
    try:
        logging.info("Embed request received")
        text = request.form['text']
        audio_file = request.files['audio']
        logging.debug(f"Text to embed: {text}")
        logging.debug(f"Audio file name: {audio_file.filename}")

        # Load audio data
        audio_data, params = load_audio(audio_file)

        # Convert text to binary with stopper
        binary_data = text_to_binary_with_stop(text)

        # Embed binary into audio
        stego_audio = embed_binary_into_audio(audio_data, binary_data)

        # Save stego audio
        stego_filename = "stego_audio.wav"
        save_audio(stego_audio, stego_filename, params)

        logging.info("Embedding completed successfully")
        return jsonify({"message": "Text embedded successfully", "file": stego_filename}), 200
    except Exception as e:
        logging.error(f"Error during embedding: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/extract', methods=['POST'])
def extract():
    try:
        logging.info("Extract request received")
        audio_file = request.files['audio']
        logging.debug(f"Audio file name: {audio_file.filename}")

        # Load audio data
        audio_data, _ = load_audio(audio_file)

        # Extract binary from audio
        extracted_binary = extract_binary_from_audio(audio_data)

        # Extract text using stopper
        extracted_text = binary_to_text_with_stop(extracted_binary)

        logging.info("Extraction completed successfully")
        return jsonify({"message": "Text extracted successfully", "text": extracted_text}), 200
    except Exception as e:
        logging.error(f"Error during extraction: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logging.info("Starting Flask server")
    app.run(debug=True)
