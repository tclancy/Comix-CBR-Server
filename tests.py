#!/usr/bin/env python

import ConfigParser
import unittest

from server import ComicServer, CBRResource


class TestComicParser(unittest.TestCase):
    def setUp(self):
        config = ConfigParser.ConfigParser()
        config.read("comix.conf")
        self.cbr = ComicServer(config.get("basics", "directory"))
    
    def test_filename_cleaner(self):
        self.assertEqual("Best of the Brave and the Bold",
                         self.cbr._prep_title("Best of the Brave and the Bold (1988)"))


if __name__ == '__main__':
    unittest.main()