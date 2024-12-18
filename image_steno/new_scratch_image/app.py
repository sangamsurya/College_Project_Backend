from flask import Flask, request, jsonify
from PIL import Image
import numpy as np
import uuid
import os

from pymongo import MongoClient
import hashlib

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")
db = client['steganography_db']
collection = db['embedded_images']


# Initialize Flask app
app = Flask(__name__)
UPLOAD_FOLDER = 'static/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Constants
END_MARKER = "11111111"  # Binary marker to signify the end of embedded data


# Function to check if the carrier image can hold the secret data
def check_capacity(carrier_array, data_length):
    capacity = carrier_array.size  # Total number of pixels * 3 (for RGB images)
    if data_length > capacity:
        raise ValueError("The carrier image does not have enough capacity to hold the secret data.")


def encode_image_and_store_with_id(image_path, secret_image_path, unique_id):
    # Open the carrier and secret images
    carrier_image = Image.open(image_path).convert("RGB")
    carrier_array = np.array(carrier_image)

    secret_image = Image.open(secret_image_path).convert("L")  # Convert to grayscale
    secret_array = np.array(secret_image)

    # Get dimensions of the secret image
    secret_height, secret_width = secret_array.shape[:2]

    # Flatten the secret image and convert to binary
    secret_flat = secret_array.flatten()
    secret_binary = ''.join([f"{pixel:08b}" for pixel in secret_flat])

    # Convert dimensions to binary (16 bits each)
    size_binary = f"{secret_height:016b}{secret_width:016b}"

    # Convert unique ID to binary (padded to 128 bits)
    unique_id_binary = ''.join(f"{ord(char):08b}" for char in unique_id).ljust(128, '0')

    # Combine unique ID, size, and image data
    full_binary_data = unique_id_binary + size_binary + secret_binary

    print(f"Unique ID binary: {unique_id_binary}")
    print(f"Binary size data: {size_binary}")
    print(f"Total binary length: {len(full_binary_data)}")

    # Check if the carrier image can hold the secret image data
    check_capacity(carrier_array, len(full_binary_data))

    # Flatten the carrier array
    flat_carrier_array = carrier_array.flatten()

    # Embed the binary data into the LSBs of the carrier image
    for i in range(len(full_binary_data)):
        flat_carrier_array[i] = (flat_carrier_array[i] & ~1) | int(full_binary_data[i])

    # Reshape the array back to the original dimensions
    encoded_carrier_array = flat_carrier_array.reshape(carrier_array.shape)
    encoded_image = Image.fromarray(encoded_carrier_array.astype('uint8'))

    # Save the encoded image
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'encoded_image_with_id.png')
    encoded_image.save(output_path, format='PNG', optimize=True)

    # Compute the hash of the secret image
    secret_image_bytes = secret_array.tobytes()
    secret_hash = hashlib.sha256(secret_image_bytes).hexdigest()
    
    # Store the secret hash and unique ID in MongoDB
    collection.insert_one({
        "unique_id": unique_id,
        "secret_hash": secret_hash,
        "secret_size": f"{secret_height}x{secret_width}"
    })

    return output_path

def extract_and_verify_image_with_id(stego_image_path):
    # Load the stego image
    stego_image = Image.open(stego_image_path).convert("RGB")
    stego_array = np.array(stego_image)

    # Flatten the stego image array to extract LSBs
    flat_stego_array = stego_array.flatten()

    # Extract the first 128 bits for the unique ID
    unique_id_binary = ''.join([str(flat_stego_array[i] & 1) for i in range(288)])
    unique_id = ''.join(chr(int(unique_id_binary[i:i + 8], 2)) for i in range(0, 288, 8)).strip('\x00')
    
    print(unique_id)

    # Query MongoDB for the original hash using the unique ID
    record = collection.find_one({"unique_id": unique_id})
    if not record:
        return {"error": "No matching record found in the database"}, 400

    # Extract the next 32 bits for dimensions (16 bits each for height and width)
    extracted_size_binary = ''.join([str(flat_stego_array[i] & 1) for i in range(288, 320)])
    secret_height = int(extracted_size_binary[:16], 2)
    secret_width = int(extracted_size_binary[16:], 2)
    print(f"Extracted size: {secret_height}x{secret_width}")

    # Calculate the number of pixels in the secret image
    num_pixels = secret_height * secret_width

    # Extract the next `num_pixels * 8` bits for the secret image
    extracted_image_binary = ''.join(
        [str(flat_stego_array[i] & 1) for i in range(320, 320 + num_pixels * 8)]
    )
    print(f"Extracted binary length: {len(extracted_image_binary)}")

    # Convert the binary data back to pixel values
    secret_flat = [int(extracted_image_binary[i:i + 8], 2) for i in range(0, len(extracted_image_binary), 8)]
    secret_array = np.array(secret_flat, dtype='uint8').reshape((secret_height, secret_width))

    # Compute the hash of the extracted secret image
    extracted_image_bytes = secret_array.tobytes()
    extracted_hash = hashlib.sha256(extracted_image_bytes).hexdigest()
    print(f"Extracted image hash: {extracted_hash}")

    secret_image = Image.fromarray(secret_array, mode='L')
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted_image.png')
    secret_image.save(output_path, format='PNG', optimize=True)
    
    # Compare the hashes
    if extracted_hash == record["secret_hash"]:
        return {"match_status": "success", "message": "Document Authenticated"}
    else:
        return {"match_status": "fail", "message": "Document Not Authenticated"}
    

# Flask Routes
@app.route('/')
def index():
    return "Hello Surya, Steganography API is running!"


@app.route('/embed', methods=['POST'])
def embed_with_id():
    if 'cover_image' not in request.files or 'secret_image' not in request.files:
        return jsonify({"error": "Please upload both the cover image and the secret image"}), 400

    cover_image = request.files['cover_image']
    secret_image = request.files['secret_image']

    # Generate a unique ID
    unique_id = str(uuid.uuid4())

    cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cover_image.jpg')
    secret_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'secret_image.jpg')

    cover_image.save(cover_image_path)
    secret_image.save(secret_image_path)

    try:
        stego_image_path = encode_image_and_store_with_id(cover_image_path, secret_image_path, unique_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Image embedded successfully",
        "unique_id": unique_id,
        "stego_image": stego_image_path
    })

@app.route('/extract', methods=['POST'])
def extract_with_id():
    if 'stego_image' not in request.files:
        return jsonify({"error": "Please upload the stego image"}), 400

    stego_image = request.files['stego_image']

    stego_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'stego_image.png')
    stego_image.save(stego_image_path)

    try:
        result = extract_and_verify_image_with_id(stego_image_path)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
