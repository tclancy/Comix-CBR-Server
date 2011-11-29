import ConfigParser
import fnmatch
import logging
import os
import re

from twisted.web import server, resource
from twisted.internet import reactor

# Setup logging
logger = logging.getLogger("comix")
logger.setLevel(logging.DEBUG)

# Use file output for production logging:
logfilename = "comix.log"
filelog = logging.FileHandler(logfilename, "w")
filelog.setLevel(logging.INFO)

# Use console for development logging:
conlog = logging.StreamHandler()
conlog.setLevel(logging.DEBUG)

# Specify log formatting:
formatter = logging.Formatter("%(asctime)s - %(message)s")
conlog.setFormatter(formatter)
filelog.setFormatter(formatter)

# Add console log to logger - TODO: check config file before turning on console logging
logger.addHandler(conlog)
logger.addHandler(filelog)

# Regexs we will need
LEADING_DIGIT_CLEANER = re.compile("^\(?\d+\.?\)?\s*")
OTHER_LEADING_DIGIT_CLEANER = re.compile("^\d+\s*\-?\s*")
BRACKET_CLEANER = re.compile("\s*[\[|(].*[\]|)]\s*")
ISSUE_RANGE_CLEANER = re.compile("\s*\d+\s*-\s*\d+\s*")
VOLUME_CLEANER = re.compile("\s*v\s{0,1}\d+\s*", re.IGNORECASE)
LONELY_APOSTROPHE_CLEANER = re.compile("\s+'\W*\s*")
HIGH_ASCII_CLEANER = re.compile("[^\\x00-\\x7f]")
ANNUALS_CLEANER = re.compile("[\s|-]+annuals.*", re.IGNORECASE)

class CBRResource(resource.Resource):
    isLeaf = True
    
    def __init__(self, directory):
        # old-skool call to parent
        resource.Resource.__init__(self)
        self.titles = {}
        
        # TODO: directory handling - make sure ends in /,
        # replace Windows separator stuff with /
        self.directory = self._normalize_directory_path(directory)
        if not os.path.exists(self.directory):
            logger.critical("%s is not a valid root directory" % self.directory)
            sys.exit(1)
        
        # ASSUMPTION: Empty folders (parents that only contain other folders or
        # non-matching files) should never be used as a key in TITLES
        self.ignored_folder_names = []
        total = 0
        
        # when you find a cbr or cbz, put folder name into titles
        # problem here: fnmatch is only case-insensitive on case-insensitive OSes - replace?
        for root, dirnames, filenames in os.walk(self.directory):
            matches = fnmatch.filter(filenames, "*.cb[r|z]")
            matches.sort()
            if not matches:
                self.ignored_folder_names.append(os.path.split(root)[-1])
            for f in matches:
                self._add_match_to_collection(f, root)
                total = total + 1
        logger.info("Found %d comics" % total)

    def render_GET(self, request):
        request.setHeader("content-type", "text/html")
        response = "Serving contents of %s" % self.directory
        for key in sorted(self.titles.iterkeys()):
            entry = self.titles[key]
            #response += "<br />%s: %d issues" % (key, entry["count"])
            response += "<br />%s" % (key)
        return response
    
    def _add_match_to_collection(self, filename, root):
        """
        For a matching file, look at its folder information. If any of the folders
        in its parent path exist in self.titles already, use that. Otherwise,
        create a new entry.
        
        Update book count and add this match to self.titles[key] files list
        
        TODO: The problem with this folder-as-title logic is that its dependent
        on the order in which the folders are matched by fnmatch.filter
        As an example, ideally all of the titles I have under E:\Comics\Indies\Nexus
        would be inside 'Nexus', but because the sub-folders are fed in first, only
        the one file in the root folder shows up there
        """
        path_info = os.path.split(root.replace(self.directory, ""))
        exists = False
        for folder in path_info:
            if folder in self.ignored_folder_names:
                continue
            folder = self._prep_title(folder)
            if self.titles.has_key(folder):
                exists = True
                self.titles[folder]["count"] = self.titles[folder]["count"] + 1
        if not exists or not self.titles.has_key(folder):
            self.titles[folder] = {"count": 1, "files": []}
        
        # ignore duplicate files
        file_list = self.titles[folder]["files"]
        file_path = os.path.join(root, filename)
        if file_path not in file_list:
            file_list.append(file_path)
    
    def _prep_title(self, folder_name):
        """
        Do some basic cleanup on the nastiness P2P folks and anal-retentives
        like to add to folders.
        
        * Get rid of underscores and # signs
        * leading digits for sorted collections (e.g., '1. A New Hope')
            how to differentiate this from a comic like 2000 A.D.?
            especially when people put years in the titles
        * Strip anything inside brackets or parens
        * Lose any number ranges (e.g., 1 - 10), regardless of space inside
        * Get rid of volume indicators for now (e.g., v2)
            might need to provide that info later in titles
        * Get rid of any apostrophes we've orphaned (e.g., '93-'96)
        * Lose high ASCII, non-alphanumeric stuff (e.g., copyright symbol)
        * Strip "Annuals" to prevent having a separate folder for those ???
        * If we're left with nothing at the end, return the original folder name
        """
        title = folder_name.replace("_", " ")
        title = folder_name.replace("#", "")
        title = LEADING_DIGIT_CLEANER.sub("", title)
        title = OTHER_LEADING_DIGIT_CLEANER.sub("", title)
        title = BRACKET_CLEANER.sub("", title)
        title = ISSUE_RANGE_CLEANER.sub("", title)
        title = VOLUME_CLEANER.sub("", title)
        title = LONELY_APOSTROPHE_CLEANER.sub("", title)
        title = HIGH_ASCII_CLEANER.sub("", title)
        title = ANNUALS_CLEANER.sub("", title)
        
        if not len(title):
            return folder_name
        return title
    
    def _normalize_directory_path(self, directory):
        """
        For Windows, get rid of \ crud
        """
        return directory.replace('\\', '/')


config = ConfigParser.ConfigParser()
try:
    config.read("comix.conf")
    port = int(config.get("basics", "port"))
    reactor.listenTCP(port, server.Site(
        CBRResource(config.get("basics", "directory")))
    )
    reactor.run()
except ConfigParser.ParsingError, e:
    print """Sorry, I couldn't find a comix.conf file in this directory.
It should contain a [basics] section with port and directory info"""
    sys.exit(1)
except ValueError, e:
    print "The value for port in comix.conf must be a number"