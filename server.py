import ConfigParser

from twisted.web import server, resource
from twisted.internet import reactor

class HelloResource(resource.Resource):
    isLeaf = True
    numberRequests = 0

    def render_GET(self, request):
        self.numberRequests += 1
        request.setHeader("content-type", "text/plain")
        return "I am request #" + str(self.numberRequests)


config = ConfigParser.ConfigParser()
try:
    config.read("comix.conf")
    port = int(config.get("basics", "port"))
    directory = config.get("basics", "directory")
    reactor.listenTCP(port, server.Site(HelloResource()))
    reactor.run()
except ConfigParser.ParsingError, e:
    print """Sorry, I couldn't find a comix.conf file in this directory.
It should contain a [basics] section with port and directory info"""
    sys.exit(1)
except ValueError, e:
    print "The value for port in comix.conf must be a number"