"""
Example SMArt REST Application: Performs OAuth, storing record-level
access tokens in the application's RDF repository.  Provides a list of
which prescriptions will need to be refilled soon (based on dispense
quantity + date, and the unrealistic simplifying assumption that one
pill per day is consumed).  

In addition to displaying friendly reminders within the SMArt
Container, this application easily be tweaked to send out reminder
e-mails when a prescription is running low.

Josh Mandel
Children's Hospital Boston, 2010
"""

import cherrypy
import datetime
import RDF
import settings
from smart_client.rdf_utils import *
from smart_client.smart import SmartClient
cp_config = "cherrypy.config.py"


"""Convenience function to initialize a new SmartClient"""
def get_smart_client(resource_tokens=None):
    return SmartClient(settings.SMART_APP_ID, 
                       settings.SMART_SERVER_PARAMS, 
                       settings.SMART_SERVER_OAUTH, 
                       resource_tokens)

"""Exposes pages through cherrypy"""
class RxReminder:

    """An OAuth start page"""
    @cherrypy.expose
    def index_html(self, record_id):        

        # Initialize a SmartClient()
        client = get_smart_client()
        params = {'offline': 'true', 'record_id': record_id}

        # Get a request token/secret pair and save them
        rt = client.get_request_token(params)
        cherrypy.session['request_token'] = rt
        cherrypy.session['record_id'] = record_id

        #Redirect to the SMArt container's authentication page
        raise cherrypy.HTTPRedirect(client.redirect_url(rt), 307)

    """Completes the OAuth dance"""
    @cherrypy.expose
    def after_auth_html(self, oauth_token, oauth_verifier):

        # Make sure the user has authorized the expected token
        stored_token = cherrypy.session['request_token']
        assert stored_token.token == oauth_token, "Authorized the wrong token."
        
        # Exchange the request token/secret for an access token/secret
        client = get_smart_client()
        client.update_token(stored_token)
        access_token = client.exchange(oauth_token, oauth_verifier)

        # Save access token/secret to RDF store in the SMArt conatiner
        client = get_smart_client()
        client.save_token(cherrypy.session['record_id'], access_token)

        # Rediret to the main view
        raise cherrypy.HTTPRedirect("rx_reminder", 307)


    """Provides a list of upcoming refills"""
    @cherrypy.expose
    def rx_reminder(self):
        client = get_smart_client()
        record_id = cherrypy.session['record_id']

        # Use the access token associated with this record
        client.update_token(client.get_tokens_for_record(record_id))

        # Find a list of all fulfillments for each med.
        q = RDF.SPARQLQuery("""
BASE <http://smartplatforms.org/>
PREFIX dc:<http://purl.org/dc/elements/1.1/>
PREFIX dcterms:<http://purl.org/dc/terms/>
PREFIX sp:<http://smartplatforms.org/>
PREFIX rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
   SELECT  ?med ?name ?fill ?quant ?when
   WHERE {
          ?med rdf:type <medication>.
          ?med dcterms:title ?name.
          ?med sp:fulfillment ?fill.
          ?fill sp:dispenseQuantity ?quant.
          ?fill dc:date ?when.
   }
""")

        # Represent the list as an RDF graph, and run the query
        meds = parse_rdf(client.get("/records/%s/medications/"%record_id))
        pills = list(q.execute(meds))

        # Find the last fulfillment date for each medication
        self.last_pill_dates = {}
        for pill in pills:
            self.update_pill_dates(pill)

        #Print a formatted list
        return self.format_last_dates()

    def update_pill_dates(self, pill):

        ISO_8601_DATETIME = '%Y-%m-%dT%H:%M:%SZ'
        def runs_out(pill):
            s = datetime.datetime.strptime(pill['when'].literal_value['string'], ISO_8601_DATETIME)
            s += datetime.timedelta(days=int(pill['quant'].literal_value['string']))
            return s

        last_day = runs_out(pill)
        if pill['name'] not in self.last_pill_dates or (last_day > self.last_pill_dates[pill['name']]):
            self.last_pill_dates[pill['name']] = last_day

    def format_last_dates(self):
        ret = ""
        for (medname, day) in self.last_pill_dates.iteritems():
            late = ""
            if day < datetime.datetime.today(): 
                late = "<i>LATE!</i> "
            ret += late+medname.literal_value['string'] + ": <b>" + day.isoformat()[:10]+"</b><br>"

        if (ret == ""): return "Up to date on all meds."
        ret =  "Refills due!<br<br>" + ret
        return ret

# Point cherrypy to the config file, and map the root URL        
cherrypy.quickstart(RxReminder(), "/", cp_config)
