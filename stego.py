"""SecureSteg engine: hide data inside the pixels of an image, with optional AES encryption.

Layout of the hidden bytes:
    "STEG" (4 bytes) | encrypted flag (1 byte) | body length (4 bytes) | body
    body = filename length (2 bytes) + filename + data        (filename is empty for text)
"""
import hashlib
import os

import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image

MAGIC = b"STEG"     # marker that tells us "this image contains our data"
HEADER_SIZE = 9     # 4 (magic) + 1 (flag) + 4 (length)


# ---------------- 1. Encryption: AES-256-GCM ----------------
def make_key(password, salt):
    """Turn a password into a 32-byte AES key. 200,000 rounds make password guessing slow."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


def encrypt(data, password):
    salt, nonce = os.urandom(16), os.urandom(12)   # random every time -> same text encrypts differently
    return salt + nonce + AESGCM(make_key(password, salt)).encrypt(nonce, data, None)


def decrypt(blob, password):
    salt, nonce, ciphertext = blob[:16], blob[16:28], blob[28:]
    try:
        return AESGCM(make_key(password, salt)).decrypt(nonce, ciphertext, None)
    except InvalidTag:   # GCM checks a tag, so a wrong password is always detected
        raise ValueError("Wrong password or corrupted data.")


# ---------------- 2. LSB: read/write the lowest bit of each colour value ----------------
def capacity(image):
    """Bytes an image can hide: 3 colour values (R, G, B) per pixel, 1 bit each, 8 bits per byte."""
    return image.width * image.height * 3 // 8


def embed(image, data):
    pixels = np.array(image.convert("RGB"))
    flat = pixels.flatten()                                     # R, G, B, R, G, B, ...
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))   # bytes -> list of 0/1
    if len(bits) > len(flat):
        raise ValueError(f"Message too big: needs {len(data):,} bytes, image holds {capacity(image):,}.")
    flat[:len(bits)] = (flat[:len(bits)] & 0b11111110) | bits   # clear the last bit, then set it
    return Image.fromarray(flat.reshape(pixels.shape))


def extract(image, n_bytes, start=0):
    """Read n_bytes hidden bytes, starting `start` bytes into the hidden data."""
    flat = np.array(image.convert("RGB")).flatten()
    bits = flat[start * 8:(start + n_bytes) * 8] & 1            # keep only the last bit
    return np.packbits(bits).tobytes()                          # list of 0/1 -> bytes


# ---------------- 3. Hide / reveal a message ----------------
def hide(image, data, filename="", password=""):
    """Return a new image with `data` hidden in it. Encrypted if a password is given."""
    name = filename.encode()
    body = len(name).to_bytes(2, "big") + name + data
    if password:
        body = encrypt(body, password)
    header = MAGIC + bytes([1 if password else 0]) + len(body).to_bytes(4, "big")
    return embed(image, header + body)


def reveal(image, password=""):
    """Return (data, filename). filename is "" when the hidden data is a text message."""
    header = extract(image, HEADER_SIZE)
    length = int.from_bytes(header[5:9], "big")
    if header[:4] != MAGIC or HEADER_SIZE + length > capacity(image):
        raise ValueError("No hidden data found in this image.\n"
                         "(JPEG images lose hidden data - use the PNG made by this app.)")
    body = extract(image, length, start=HEADER_SIZE)
    if header[4] == 1:
        if not password:
            raise ValueError("This data is encrypted - enter the password.")
        body = decrypt(body, password)
    name_len = int.from_bytes(body[:2], "big")
    filename = os.path.basename(body[2:2 + name_len].decode())   # drop any folder names
    return body[2 + name_len:], filename


# ---------------- 4. Image quality ----------------
def quality(original, stego):
    """MSE (average squared pixel change) and PSNR in dB (higher = harder to see; > 40 is invisible)."""
    a = np.array(original.convert("RGB"), dtype=float)
    b = np.array(stego.convert("RGB"), dtype=float)
    mse = np.mean((a - b) ** 2)
    psnr = float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
    return mse, psnr
