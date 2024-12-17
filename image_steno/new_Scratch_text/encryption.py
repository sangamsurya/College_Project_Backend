from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()


def encrypt_text(key, text):
    cipher = Fernet(key)
    encrypted_text = cipher.encrypt(text.encode())
    return encrypted_text


def decrypt_text(key, encrypted_text):
    cipher = Fernet(key)
    text = None
    try:
        print("Attempting decryption...")
        print("Key:", key)
        print("Encrypted Text:", encrypted_text)
        text = cipher.decrypt(encrypted_text).decode()
    except Exception as e:
        print("Decryption failed:", str(e))
    return text


def encryption(text):
    secret_key = generate_key()
    encrypted_message = encrypt_text(secret_key, text)

    return encrypted_message,secret_key

