# 🔒 SecureSteg

A desktop app that **hides a text message or any file inside an image** (steganography),
with optional **AES-256 encryption**, user accounts and a history of everything you did.

Built with Python, Tkinter (GUI), NumPy, Pillow (images), SQLite (database) and `cryptography`.

## Run it
```bash
pip install -r requirements.txt
python app.py              # start the app
python -m unittest         # run the tests
```

## Files
| File             | What it does |
|------------------|--------------|
| `stego.py`       | The engine: encryption, hiding bits in pixels, hide/reveal, image quality |
| `database.py`    | SQLite: user accounts (hashed passwords) and history |
| `app.py`         | The window: login screen + Encode / Decode / History tabs |
| `test_stego.py`  | Automatic tests for `stego.py` and `database.py` |

`app.py` only handles buttons and text boxes; all the real work is in `stego.py` and `database.py`.

## How it works

### 1. LSB steganography (hiding bits in pixels)
Every pixel has 3 colour values (Red, Green, Blue), each a number 0-255 = 8 bits.
We replace the **last bit** (Least Significant Bit) of each value with one bit of our message.

```
Red = 200 = 11001000   message bit = 1   ->   11001001 = 201
```
A colour changes by at most 1 out of 255, which the eye cannot see.
**Capacity** = width × height × 3 bits = width × height × 3 / 8 bytes.
Example: an 800×600 image can hide about 175 KB.

In code (`embed`): `(value & 0b11111110) | bit` — clear the last bit, then put our bit there.
Reading back (`extract`): `value & 1` — keep only the last bit.

### 2. What gets hidden
```
"STEG" | encrypted flag | body length | body
4 bytes     1 byte          4 bytes
```
- `"STEG"` is a marker. If it's missing, the image has no hidden data.
- The length tells the decoder how many bytes to read.
- `body` = filename length + filename + data. The filename is empty for a text message.

### 3. Encryption (AES-256-GCM)
- The password is turned into a 256-bit key with **PBKDF2** (200,000 rounds of SHA-256, so guessing passwords is slow).
- A random **salt** and **nonce** are generated each time, so the same message encrypts differently every time.
- **GCM** adds an authentication tag, so a **wrong password is always detected**.
- Encryption hides *what* the message says; LSB hides *that there is* a message.

### 4. User accounts
Passwords are never stored. We store a random salt and `PBKDF2(password, salt)`.
At login we hash the typed password the same way and compare the two hashes.

### 5. Image quality (shown after encoding)
- **MSE**: the average squared change per colour value. Close to 0 means almost nothing changed.
- **PSNR** = 10·log10(255² / MSE), in dB. Above 40 dB means the change can't be seen. LSB usually gives about 51 dB or more.

## Important notes
- The output is always **PNG**. JPEG compression changes pixel values and destroys the hidden bits.
- Limitation: plain LSB can be detected by statistical tools (steganalysis). Encryption still keeps the content safe.
