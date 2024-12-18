from flask import Flask,request,jsonify
from pymongo import MongoClient
import os
import base64

from encryption import encryption
from stenography import encode_image,decode_image

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

client = MongoClient("mongodb://localhost:27017/")
db = client["document_new"]
collection = db["metadata"]

@app.route('/')
def hello():
    return 'Hello, i am Surya '

@app.route('/encode', methods=['POST'])
def encode():
    file = request.files['file']
    signature = request.form['signature']
    print(signature)
    encrypted_text,key = encryption(signature)
    print(encrypted_text,key)

    encrypted_text_b64 = base64.b64encode(encrypted_text).decode('utf-8')
    key_b64 = base64.b64encode(key).decode('utf-8')

    unique_id,encoded_path = encode_image(file,encrypted_text)
    metadata = {
        "unique_id": unique_id,
        "encrypted_signature": encrypted_text_b64,
        "file_path": encoded_path,
        "original_filename": file.filename,
        "key":key_b64
    }
    collection.insert_one(metadata)

    return jsonify({"status": "success", "message": "File uploaded", "stego_file": encoded_path})


@app.route('/decode', methods=['POST'])
def decode():
    file = request.files['file']

    # Decode the image to get unique ID and text
    unique_id, decoded_text = decode_image(file)

    # Find the document using the unique ID
    document = collection.find_one({"unique_id": unique_id})
    if not document:
        return jsonify({"status": "fail", "message": "Document Not Authenticated or Not found"}), 404

    # Retrieve the stored encrypted signature and key
    stored_signature = base64.b64decode(document['encrypted_signature'])
    key = base64.b64decode(document['key'])

    # Ensure decoded_text is a string
    # Convert decoded_text properly to remove the b'...' artifacts if present
    
    decoded_string = decoded_text.strip("b'").strip("'")

    # Decode the stored signature into a string
    stored_string = stored_signature.decode('utf-8', errors='ignore')

    # Debugging logs
    print("Decoded Text (Clean String):", decoded_string)
    print("Stored Signature (String):", stored_string)
    print("Comparison Result:", decoded_string == stored_string)

    # Compare decoded text with stored signature
    if decoded_string == stored_string:
        return jsonify({"status": "success", "message": "Document Authenticated"}), 200
    else:
        return jsonify({"status": "fail", "message": "Document Not Authenticated"}), 404

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)


