"""Tests for the engine and the database.   Run:  python -m unittest"""
import unittest

import numpy as np
from PIL import Image

import stego
from database import Database


def random_image(width=100, height=100):
    pixels = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


class TestStego(unittest.TestCase):
    def setUp(self):
        self.image = random_image()

    def test_text(self):
        result = stego.hide(self.image, b"hello world")
        self.assertEqual(stego.reveal(result), (b"hello world", ""))

    def test_file(self):
        result = stego.hide(self.image, b"%PDF data", filename="report.pdf")
        self.assertEqual(stego.reveal(result), (b"%PDF data", "report.pdf"))

    def test_encrypted(self):
        result = stego.hide(self.image, b"secret", password="pass1234")
        self.assertEqual(stego.reveal(result, "pass1234"), (b"secret", ""))

    def test_wrong_or_missing_password(self):
        result = stego.hide(self.image, b"secret", password="pass1234")
        with self.assertRaises(ValueError):
            stego.reveal(result, "wrong")
        with self.assertRaises(ValueError):
            stego.reveal(result)

    def test_no_hidden_data(self):
        with self.assertRaises(ValueError):
            stego.reveal(self.image)

    def test_message_too_big(self):
        with self.assertRaises(ValueError):
            stego.hide(random_image(10, 10), b"x" * 1000)

    def test_pixels_change_by_at_most_one(self):
        result = stego.hide(self.image, b"x" * 500)
        diff = np.abs(np.array(self.image, dtype=int) - np.array(result, dtype=int))
        self.assertLessEqual(diff.max(), 1)
        mse, psnr = stego.quality(self.image, result)
        self.assertGreater(psnr, 40)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")   # temporary database in RAM

    def test_register_and_login(self):
        self.db.register("alice", "password123")
        self.assertIsInstance(self.db.login("alice", "password123"), int)
        with self.assertRaises(ValueError):
            self.db.login("alice", "wrongpass")
        with self.assertRaises(ValueError):
            self.db.register("alice", "another123")   # username taken
        with self.assertRaises(ValueError):
            self.db.register("bob", "short")          # password too short

    def test_history(self):
        self.db.register("alice", "password123")
        user = self.db.login("alice", "password123")
        self.db.add_history(user, "C:/pics/cat.png", "encode", True)
        self.db.add_history(user, "C:/pics/dog.png", "decode", False)
        self.assertEqual(len(self.db.get_history(user)), 2)
        self.assertEqual(self.db.get_history(user, "cat")[0][3], "C:/pics/cat.png")


if __name__ == "__main__":
    unittest.main()
