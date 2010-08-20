"""
RDF Parsing utils for SMArt
Josh Mandel
joshua.mandel@childrens.harvard.edu
"""

import urllib
import RDF


NS = {}
NS['dc'] = RDF.NS('http://purl.org/dc/elements/1.1/')
NS['dcterms'] = RDF.NS('http://purl.org/dc/terms/')
NS['med'] = RDF.NS('http://smartplatforms.org/medication#')
NS['umls'] = RDF.NS('http://www.nlm.nih.gov/research/umls/')
NS['sp'] = RDF.NS('http://smartplatforms.org/')
NS['foaf']=RDF.NS('http://xmlns.com/foaf/0.1/')
NS['rdf'] = RDF.NS('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
NS['rxn'] = RDF.NS('http://link.informatics.stonybrook.edu/rxnorm/')
NS['rxcui'] = RDF.NS('http://link.informatics.stonybrook.edu/rxnorm/RXCUI/')
NS['rxaui'] = RDF.NS('http://link.informatics.stonybrook.edu/rxnorm/RXAUI/')
NS['rxatn'] = RDF.NS('http://link.informatics.stonybrook.edu/rxnorm/RXATN#')
NS['rxrel'] = RDF.NS('http://link.informatics.stonybrook.edu/rxnorm/REL#')
NS['ccr'] = RDF.NS('urn:astm-org:CCR')

def serialize_rdf(model):
    serializer = bound_serializer()    
    try: return serializer.serialize_model_to_string(model)
    
    except AttributeError:
      try:
          tmpmodel = RDF.Model()
          tmpmodel.add_statements(model.as_stream())
          return serializer.serialize_model_to_string(tmpmodel)
      except AttributeError:
          return '<?xml version="1.0" encoding="UTF-8"?>'

def bound_serializer():
    s = RDF.RDFXMLSerializer()
    bind_ns(s)
    return s 

def bind_ns(serializer, ns=NS):
    for k in ns.keys():
        v = ns[k]
        serializer.set_namespace(k, RDF.Uri(v._prefix))

def parse_rdf(string, model=None, context="none"):
    if model == None:
        model = RDF.Model() 
    parser = RDF.Parser()
    try:
        parser.parse_string_into_model(model, string.encode(), context)
    except  RDF.RedlandError: pass
    return model

def get_property(model, s, p):
    r = list(model.find_statements(
            RDF.Statement(
                s, 
                p,
                None)))
    assert len(r) == 1, "Expect only one %s on subject %s"%(p, s)

    node = r[0].object
    if (node.is_resource()):
        return node.uri
    elif (node.is_blank()):
        return node.blank_identifier
    else: #(node.is_literal()):
        return node.literal_value['string']

