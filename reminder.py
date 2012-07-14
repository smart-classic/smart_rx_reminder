"""
Example SMART REST Application: Parses OAuth tokens from
browser-supplied cookie, then provides a list of which prescriptions
will need to be refilled soon (based on dispense day's supply + date).

Josh Mandel
Children's Hospital Boston, 2010
"""
import sys, os
import datetime
from smart_client.client import SMARTClient
import tempfile
import web
web.config.debug = False

"""
 A SMART app serves at least two URLs: 
   * "index.html" page to supply the UI.
   * "after_auth" page to supply the UI.
"""
urls = ('/smartapp/index.html',     'BeginOAuthDance',
        '/smartapp/after_auth',     'RxReminder')

app = web.application(urls, globals())
session_store = web.session.DiskStore("session")
session = web.session.Session(app, session_store)

# Basic configuration:  the consumer key and secret we'll use
# to OAuth-sign requests.
CONSUMER_PARAMS = {
        'consumer_key': 'rx-reminder@apps.smartplatforms.org',
        'consumer_secret': 'smartapp-secret'
        }

# Exposes pages through web.py
class BeginOAuthDance:

    """An SMART REST App start page"""
    def GET(self):

        # This is how we know... what container we're talking to
        api_base = web.input().api_base
        client = get_smart_client(api_base, CONSUMER_PARAMS) 

        params = {  
                'oauth_callback':'http://localhost:8000/smartapp/after_auth',
                'smart_record_id': web.input().record_id
                }

        session.request_token = client.fetch_request_token(params)
        session.api_base = client.api_base
        return web.redirect(client.auth_redirect_url)


def complete_oauth_dance():

    # Already have access tokens -- read info from existing session
    if session.get('access_token', False) and \
       session.get('record_id', False) and \
       session.get('user_id', False): 

        return get_smart_client(session.api_base,
                CONSUMER_PARAMS,
                resource_token=session.access_token,
                record_id=session.record_id,
                user_id=session.user_id) 

    # Need to get access tokens for the 1st time
    else:
        # get the token and verifier from the URL parameters
        oauth_token = web.input().oauth_token
        oauth_verifier = web.input().oauth_verifier

        # retrieve request token stored in the session
        request_token = session.request_token

        # is this the right token?
        if request_token['oauth_token'] != oauth_token:
            return "uh oh bad token"

        # get the SMART client and use the request token as the token for the exchange
        client = get_smart_client(session.api_base, 
                CONSUMER_PARAMS, 
                resource_token=request_token) 

        client.exchange_token(oauth_verifier) 

        session.access_token = client.token
        session.record_id = client.record_id
        session.user_id = client.user_id

        return client

class RxReminder:
    """An SMART REST App start page"""
    def GET(self):

        client = complete_oauth_dance()

        # Represent the list as an RDF graph
        meds = client.records_X_medications_GET()
        print "Triples: ", len(meds.graph)

        # Find a list of all fulfillments for each med.
        q = """
            PREFIX dcterms:<http://purl.org/dc/terms/>
            PREFIX sp:<http://smartplatforms.org/terms#>
            PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
               SELECT  ?med ?name ?quant ?when
               WHERE {
                      ?med rdf:type sp:Medication .
                      ?med sp:drugName ?medc.
                      ?medc dcterms:title ?name.
                      ?med sp:fulfillment ?fill.
                      ?fill sp:dispenseDaysSupply ?quant.
                      ?fill dcterms:date ?when.
               }
            """
        pills = meds.graph.query(q)

        # Find the last fulfillment date for each medication
        self.last_pill_dates = {}

        for pill in pills:
            self.update_pill_dates(*pill)

        #Print a formatted list
        return header + self.format_last_dates() + footer

    def update_pill_dates(self, med, name, quant, when):        
        ISO_8601_DATETIME = '%Y-%m-%d'
        def runs_out():
            print>>sys.stderr, "Date", when
            s = datetime.datetime.strptime(str(when), ISO_8601_DATETIME)
            s += datetime.timedelta(days=int(float(str(quant))))
            return s

        r = runs_out()
        previous_value = self.last_pill_dates.setdefault(name, r)
        if r > previous_value:
            self.last_pill_dates[name] = r


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
  <head>                     <script src="http://sample-apps.smartplatforms.org/framework/smart/scripts/smart-api-client.js"></script></head>
  <body>
"""

footer = """
</body>
</html>"""


"""Convenience function to initialize a new SMARTClient"""
def get_smart_client(api_base,consumer_params, resource_token=None, *args, **kwargs):

    return SMARTClient(api_base, 
            consumer_params,
            resource_token,
            *args, 
            **kwargs)

    if __name__ == "__main__":
        app.run()
else:
    application = app.wsgifunc()
