"""
Example SMArt REST Application: Parses OAuth tokens from
browser-supplied cookie, then provides a list of which prescriptions
will need to be refilled soon (based on dispense quantity + date, and
the unrealistic simplifying assumption that one pill per day is
consumed).

Josh Mandel
Children's Hospital Boston, 2010
"""

import web, RDF, urllib
import datetime
import smart_client
from smart_client import oauth
from smart_client.smart import SmartClient
from smart_client.common.util import serialize_rdf

# Basic configuration:  the consumer key and secret we'll use
# to OAuth-sign requests.
SMART_SERVER_OAUTH = {'consumer_key': 'developer-sandbox@apps.smartplatforms.org', 
                      'consumer_secret': 'smartapp-secret'}


# The SMArt contianer we're planning to talk to
SMART_SERVER_PARAMS = {
    'api_base' :          'http://sandbox-api.smartplatforms.org'
}


"""
 A SMArt app serves at least two URLs: 
   * "bootstrap.html" page to load the client library
   * "index.html" page to supply the UI.
"""
urls = ('/smartapp/bootstrap.html', 'bootstrap',
        '/smartapp/index.html',     'RxReminder')


# Required "bootstrap.html" page just includes SMArt client library
class bootstrap:
    def GET(self):
        return """<!DOCTYPE html>
                   <html>
                    <head>
                     <script src="http://sample-apps.smartplatforms.org/framework/smart/scripts/smart-api-client.js"></script>
                    </head>
                    <body></body>
                   </html>"""


# Exposes pages through web.py
class RxReminder:

    """An SMArt REST App start page"""
    def GET(self):
        # Fetch and use
        cookie_name = web.input().cookie_name
        smart_oauth_header = web.cookies().get(cookie_name)
        smart_oauth_header = urllib.unquote(smart_oauth_header)
        client = get_smart_client(smart_oauth_header)
        
        # Represent the list as an RDF graph
        meds = client.records_X_medications_GET()
        
        # Find a list of all fulfillments for each med.
        q = """
            PREFIX dc:<http://purl.org/dc/elements/1.1/>
            PREFIX dcterms:<http://purl.org/dc/terms/>
            PREFIX sp:<http://smartplatforms.org/terms#>
            PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
               SELECT  ?med ?name ?quant ?when
               WHERE {
                      ?med rdf:type sp:Medication .
                     ?med sp:code ?medc.
                      ?medc dcterms:title ?name.
                      ?med sp:fulfillment ?fill.
                      ?fill sp:dispenseQuantity ?quant.
                      ?fill dc:date ?when.
               }
            """
        pills = RDF.SPARQLQuery(q).execute(meds)
        
        # Find the last fulfillment date for each medication
        self.last_pill_dates = {}
        for pill in pills:
            self.update_pill_dates(pill)

        #Print a formatted list
        return header + self.format_last_dates() + footer

    def update_pill_dates(self, pill):        
        ISO_8601_DATETIME = '%Y-%m-%dT%H:%M:%SZ'
        def runs_out(pill):
            print "Date", str(pill['when'])
            s = datetime.datetime.strptime(str(pill['when']), ISO_8601_DATETIME)
            s += datetime.timedelta(days=int(float(str(pill['quant']))))
            return s

        r = runs_out(pill)
        previous_value = self.last_pill_dates.setdefault(pill['name'], r)
        if r > previous_value:
            self.last_pill_dates[pill['name']] = r


    def format_last_dates(self):
        ret = ""
        for (medname, day) in self.last_pill_dates.iteritems():
            late = ""
            if day < datetime.datetime.today(): 
                late = "<i>LATE!</i> "
            ret += late+str(medname)+ ": <b>" + day.isoformat()[:10]+"</b><br>"

        if (ret == ""): return "Up to date on all meds."
        ret =  "Refills due!<br><br>" + ret
        return ret


header = """<!DOCTYPE html>
<html>
  <head>                     <script src="http://sample-apps.smartplatforms.org/framework/smart/scripts/smart-api-page.js"></script></head>
  <body>
"""

footer = """
</body>
</html>"""


"""Convenience function to initialize a new SmartClient"""
def get_smart_client(authorization_header, resource_tokens=None):
    authorization_header = authorization_header.split("Authorization: ",1)[1]
    oa_params = oauth.parse_header(authorization_header)
    
    resource_tokens={'oauth_token':       oa_params['smart_oauth_token'],
                     'oauth_token_secret':oa_params['smart_oauth_token_secret']}

    ret = SmartClient(SMART_SERVER_OAUTH['consumer_key'], 
                       SMART_SERVER_PARAMS, 
                       SMART_SERVER_OAUTH, 
                       resource_tokens)
    
    ret.record_id=oa_params['smart_record_id']
    return ret

app = web.application(urls, globals())
if __name__ == "__main__":
    app.run()
