import ConfigParser
import fnmatch
import logging
import os

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
        
        # when you find a cbr or cbz, put folder name into titles
        self.files = []
        for root, dirnames, filenames in os.walk(self.directory):
            matches = fnmatch.filter(filenames, "*.cb[r|z]")
            for f in matches:
                self.files.append(os.path.join(root, f))
        logger.info("Found %d files" % len(self.files))

    def render_GET(self, request):
        request.setHeader("content-type", "text/html")
        response = "Serving contents of %s" % self.directory
        for d in self.files:
            response += "<br />%s" % d
        return response
    
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