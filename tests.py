#!/usr/bin/env python

import unittest

from server import CBRResource


class TestComicParser(unittest.TestCase):
    def setUp(self):
        self.cbr = CBRResource("E:/Comics/")
    
    def test_filename_cleaner(self):
        self.assertEqual("Best of the Brave and the Bold",
                         self.cbr._prep_title("Best of the Brave and the Bold (1988)"))


if __name__ == '__main__':
    unittest.main()