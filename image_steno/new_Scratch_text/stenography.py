from PIL import Image
import numpy as np
import base64
import uuid

output_path = 'uploads/encoded_image.png'

def encode_image(image_path, text):
    # Open the image and convert it to a numpy array
    image = Image.open(image_path)
    img_array = np.array(image)
    
    # Generate a unique identifier (UUID)
    unique_id = str(uuid.uuid4())
    
    # Combine the unique ID and the encrypted text
    combined_data = f"{unique_id}:{text}"
    
    # Base64 encode the combined data
    combined_data_base64 = base64.b64encode(combined_data.encode('utf-8')).decode('utf-8')
    
    # Convert the base64 data to binary
    combined_data_binary = ''.join(format(byte, '08b') for byte in combined_data_base64.encode())
    
    # Flatten the image array
    flat_img = img_array.flatten()
    
    # Ensure the image has enough capacity
    if len(combined_data_binary) > len(flat_img):
        raise ValueError("Data is too large to hide in this image.")
    
    # Modify the least significant bits
    for i in range(len(combined_data_binary)):
        flat_img[i] = (flat_img[i] & ~1) | int(combined_data_binary[i])
    
    # Reshape back and save the image
    encoded_img = flat_img.reshape(img_array.shape)
    encoded_image = Image.fromarray(encoded_img.astype('uint8'))
    encoded_image.save(output_path, format='PNG')
    
    return unique_id, output_path


def decode_image(image_path):
    # Open the image and convert it to a numpy array
    image = Image.open(image_path)
    img_array = np.array(image)
    
    # Flatten the image array and extract the least significant bits
    flat_img = img_array.flatten()
    bits = [flat_img[i] & 1 for i in range(len(flat_img))]
    
    # Group bits into bytes
    bytes_list = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        if len(byte) == 8:
            bytes_list.append(int(''.join(map(str, byte)), 2))
    
    # Convert the byte array to binary data
    combined_data = bytes(bytes_list)
    
    # Decode the base64-encoded data
    try:
        decoded_data = base64.b64decode(combined_data).decode('utf-8')
    except (base64.binascii.Error, UnicodeDecodeError):
        return ({"status": "fail", "message": "Document Not Authenticated"}), 404

    
    # Now split the decoded string into unique ID and encrypted text
    try:
        unique_id, encrypted_text = decoded_data.split(':', 1)
        return unique_id, encrypted_text
    except ValueError:
        raise ValueError("The extracted data doesn't have the correct format (unique ID and encrypted text).")
