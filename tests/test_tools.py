"""Unit tests for the tokenizer in tools.py. Nothing here touches the API."""

import unittest

from tools import tokenize


class TokenizeTests(unittest.TestCase):
    def test_short_level_token_with_digit_is_kept(self):
        self.assertIn("l5", tokenize("top of the L5 salary band"))

    def test_short_employee_id_with_digit_is_kept(self):
        self.assertIn("e005", tokenize("colleague Meera Nair (E005)"))

    def test_only_stopwords_and_short_words_gives_empty_set(self):
        self.assertEqual(tokenize("a of to the"), set())


if __name__ == "__main__":
    unittest.main()
