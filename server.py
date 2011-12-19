#!/usr/bin/env python

import ConfigParser
import fnmatch
import logging
import os
import rarfile
import re
import sys
import zipfile

from twisted.web import server, resource
from twisted.web.error import NoResource
from twisted.internet import reactor, error as twistedErrors

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

try:
    f = open("template.html", "r")
    template = f.read()
    f.close()
except IOError:
    logger.critical("Could not find template.html in this directory")
    sys.exit(1)

class ComicServer(resource.Resource):
    def __init__(self, directory):
        # old-skool call to parent
        resource.Resource.__init__(self)
        self.titles = {}
        
        # TODO: directory handling - make sure ends in /,
        # replace Windows separator stuff with /
        self.directory = self._normalize_directory_path(directory)
        if not os.path.exists(self.directory):
            logger.critical("%s is not a valid path for the root directory" % self.directory)
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
    
    def getChild(self, url, request):
        response = CBRResource(url, request, self)
        if response:
            return response
        return NoResource()
        
    
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
            key = self._slugify(folder)
            if self.titles.has_key(key):
                exists = True
                self.titles[key]["count"] = self.titles[key]["count"] + 1
        if not exists or not self.titles.has_key(key):
            self.titles[key] = {"count": 1, "files": {}, "full title": folder}
        
        # ignore duplicate files
        file_list = self.titles[key]["files"]
        file_path = os.path.join(root, filename)
        file_key = self._slugify(filename)
        if file_key not in file_list:
            file_list[file_key] = file_path
    
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
    
    def _slugify(self, value):
        value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
        return re.sub('[-\s]+', '-', value)


class CBRResource(resource.Resource):
    isLeaf = True
    
    def __init__(self, url, request, parent):
        self.url = url
        self.request = request
        self.parent = parent

    def render_GET(self, request):
        request.setHeader("content-type", "text/html")
        response = self.get_matching_response(request.path)
        if (not response
            or not hasattr(response, "has_key") or not response.has_key("body")):
            return None
        return template % {
            "title": str(response["title"]),
            "body": str(response["body"])
        }
    
    def get_matching_response(self, path):
        request_info = filter(None, path.split("/"))
        if request_info:
            top_folder = request_info[0]
            if top_folder == "favicon.ico":
                return None
            if top_folder == "read" and len(request_info) == 3:
                return self.request_file(request_info[1], request_info[2])
            if top_folder in self.parent.titles.keys():
                return self.request_title(top_folder)
        return self.request_root()
    
    def request_root(self):
        response = "Serving contents of %s<ul>" % self.parent.directory
        for key in sorted(self.parent.titles.iterkeys()):
            entry = self.parent.titles[key]
            response += '<li><a href="/%s/">%s</a>: %d issues</li>' % (key,
                                            entry["full title"], entry["count"])
        response += "</ul>"
        return {
            "body": response,
            "title": "Comix Server"
        }
    
    def request_title(self, title_key):
        entry = self.parent.titles[title_key]
        title = entry["full title"]
        content = "<h1>%s</h1><ul>" % (title)
        for key in entry["files"].keys():
            content += '<li><a href="/read/%s/%s/">%s</a></li>' % (title_key,
                                                key, entry["files"][key])
        content += "</ul>"
        return {
            "body": content,
            "title": title
        }
    
    def request_file(self, title_key, file_key):
        if not self.parent.titles.has_key(title_key):
            return None
        entry = self.parent.titles[title_key]
        issue = entry["files"].get(file_key, None)
        if not issue:
            return None
        path = issue
        file_contents = self._open_issue(issue)
        if not file_contents:
            return None
        content = "<h1>Files in %s</h1><ul>" % (path)
        for f in file_contents:
            content += "<li>%s</li>" % f
        content += "</ul>"
        return {
            "body": content,
            "title": path
        }
    
    def _open_issue(self, path):
        """
        Open issue file based on extension
        .cbr = RAR file
        .cbz = ZIP file
        See full file description at http://en.wikipedia.org/wiki/Comic_Book_Archive_file
        TODO: Handle additional types
        .cb7 = 7z
        .cbt = TAR
        .cba = ACE
        """
        if not os.path.exists(path):
            return None
        extension = path.lower()[-3:]
        if extension == "cbz":
            try:
                z = zipfile.ZipFile(path)
                return z.namelist()
            except zipfile.BadZipfile:
                return None
        if extension == "cbr":
            rf = rarfile.RarFile(path)
            return [f.filename for f in rf.infolist() if f.filename != "README"]
        return None


# run as script
if __name__ == '__main__':
    config = ConfigParser.ConfigParser()
    try:
        config.read("comix.conf")
        port = int(config.get("basics", "port"))
        try:
            reactor.listenTCP(port, server.Site(
                ComicServer(config.get("basics", "directory")))
            )
            reactor.run()
        except twistedErrors.CannotListenError:
            logger.critical("Could not listen on port %d. Is something else running there?" % port)
            sys.exit(1)
    except ConfigParser.ParsingError, e:
        logger.critical("""Sorry, I couldn't find a comix.conf file in this directory.
    It should contain a [basics] section with port and directory info""")
        sys.exit(1)
    except ValueError, e:
        logger.critical("The value for port in comix.conf must be a number")
        sys.exit(1)