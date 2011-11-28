import ConfigParser

from twisted.web import server, resource
from twisted.internet import reactor

class CBRResource(resource.Resource):
    isLeaf = True
    
    def __init__(self, directory):
        # old-skool call to parent
        resource.Resource.__init__(self)
        self.directory = directory

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        return "Serving contents of %s" % self.directory


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