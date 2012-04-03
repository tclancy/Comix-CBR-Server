#!/usr/bin/env python

import ConfigParser
import unittest

from server import ComicServer, CBRResource, IMAGE_FILE_EXTENSION_RE


class TestComicParser(unittest.TestCase):
    def setUp(self):
        config = ConfigParser.ConfigParser()
        config.read("comix.conf")
        self.cbr = ComicServer(config.get("basics", "directory"))
    
    def test_filename_cleaner(self):
        self.assertEqual("Best of the Brave and the Bold",
                         self.cbr._prep_title("Best of the Brave and the Bold (1988)"))


class TestCBRResource(unittest.TestCase):
    def test_file_filter(self):
        
        names = [
            "superman_-_whatever_happend_to_the_man_of_tomorrow_(alan_moore)\SupermanWHTTMoT-55 Whatever Happened To The Man of Tomorrow.jpg",
            "superman_-_whatever_happend_to_the_man_of_tomorrow_(alan_moore)\Thumbs.db",
            "superman_-_whatever_happend_to_the_man_of_tomorrow_(alan_moore)\\"
        ]
        results = [f for f in names if IMAGE_FILE_EXTENSION_RE.search(f)]
        self.assertEqual(1, len(results))
        self.assertEqual(names[0], results[0])


if __name__ == '__main__':
    unittest.main()