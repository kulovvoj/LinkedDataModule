import json
import requests

from collections import OrderedDict
from SPARQLWrapper import SPARQLWrapper, JSON
from nltk.corpus import wordnet
from nltk.stem import SnowballStemmer
from nltk.tokenize import word_tokenize
import sys

# Takes in a word and stemms it
def stemm_word(word):
    stemmer = SnowballStemmer("english")
    word_token = word_tokenize(word)
    return stemmer.stem(word_token[0])


# Returns a list of synonyms of a word
def get_synonyms(word):
    synonyms = [word]
    for syn in wordnet.synsets(word):
        for lm in syn.lemmas():
            synonyms.append(lm.name())
    return list(OrderedDict.fromkeys(synonyms))


# Returns all possible stemmed strings
def get_stemm_combinations_rec(stemmed_string, word_list):
    if not word_list:
        return [stemmed_string]
    if stemmed_string == "":
        result_list = get_stemm_combinations_rec(word_list[0], word_list[1:])
        result_list.extend(get_stemm_combinations_rec(stemm_word(word_list[0]), word_list[1:]))
    else:
        result_list = get_stemm_combinations_rec(stemmed_string + " " + word_list[0], word_list[1:])
        result_list.extend(get_stemm_combinations_rec(stemmed_string + " " + stemm_word(word_list[0]), word_list[1:]))
    return result_list


def get_stemm_combinations(words):
    if (not words):
        return []
    word_list = words.split()
    return get_stemm_combinations_rec("", word_list)

# Returns all the existing matching properties of the entity uri
def get_prop_uri_list(uri, prop):
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    query = """   
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?value
            WHERE { 
                <""" + uri + """> ?value ?x .
                ?value a rdf:Property .
                ?value rdfs:label ?name . 
                FILTER(bif:contains(?name, \'\"""" + prop + """\"\'))  
            }
            """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    global result
    result = list()
    a = sparql.query()
    results = a.convert()

    # parsing for dbpedia
    for data in results["results"]["bindings"]:
        result.append(data["value"]["value"])
    # removing redundant data from the result set, by using set function and then converting it to a list
    result = list(set(result))
    return result

# Returns all the entity URIs, who's labels match the entity name

def get_entity_uri_list(entity):
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    # Right now relevance is decided by number of pages in other languages
    query = """               
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?value (COUNT(?s) as ?relevance)
            WHERE { 
                {
                    ?temp rdfs:label ?name . 
                    FILTER(bif:contains(?name, \"\'""" + entity + """\'\") && strstarts(str(?temp), "http://dbpedia.org/resource/"))
                    ?temp dbo:wikiPageDisambiguates ?value .
                    ?value owl:sameAs ?s
                } UNION {
                    ?temp rdfs:label ?name . 
                    FILTER(bif:contains(?name, \"\'""" + entity + """\'\") && strstarts(str(?temp), "http://dbpedia.org/resource/"))
                    ?temp dbo:wikiPageRedirects ?value .
                    ?value owl:sameAs ?s
                } UNION {
                    ?value rdfs:label ?name . 
                    FILTER(bif:contains(?name, \"\'""" + entity + """\'\") && strstarts(str(?value), "http://dbpedia.org/resource/")) .
                    FILTER NOT EXISTS{?value dbo:wikiPageDisambiguates ?x} .
                    FILTER NOT EXISTS{?value dbo:wikiPageRedirects ?y} .
                    ?value owl:sameAs ?s
                } 
            } ORDER BY DESC(?relevance)
            """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    global result
    result = list()
    a = sparql.query()
    results = a.convert()

    # parsing for dbpedia
    for data in results["results"]["bindings"]:
        result.append(data["value"]["value"])

    # removing redundant data from the result set, by using set function and then converting it to a list
    result = list(result)
    return result

# Fetches the data of given triplet
def SPARQL_data(uri, prop):
    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?value WHERE
            { 
                { 
                    <""" + uri + """> <""" + prop + """> ?value .
                    FILTER ((LANG(?value) = "en") || !(datatype(?value) = xsd:string)) .
                } UNION {
                    <""" + uri + """> <""" + prop + """> ?temp .
                    ?temp rdfs:label ?value
                    FILTER (isURI(?temp)) .
                    FILTER ((LANG(?value) = "en")) .
                }
            }
            """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    global result
    result = list()
    a = sparql.query()
    results = a.convert()

    # parsing for dbpedia
    for data in results["results"]["bindings"]:
        result.append(data["value"]["value"])

    # removing redundant data from the result set, by using set function and then converting it to a list
    result = list(set(result))
    return result



def get_answer_data(entity, prop = None):
    abstract = "http://dbpedia.org/ontology/abstract"
    entity_uri_list = None
    # Try to get the entity URIs
    for e in get_stemm_combinations(entity):
        if (not entity_uri_list):
            entity_uri_list = get_entity_uri_list(e)
    # Continue if you found some entities
    if (entity_uri_list):
        # If you've been given property, try to find it in all the found entities
        if (prop):
            prop_uri_list = None
            for e in entity_uri_list:
                for p in get_synonyms(prop):
                    if (not prop_uri_list):
                        prop_uri_list = get_prop_uri_list(e, p)
                        entity_uri = e
            # If you've found the property, fetch the data
            if (prop_uri_list):
                res = (SPARQL_data(entity_uri, prop_uri_list[0]))
            # Else fetch the abstract data of the most relevant entity
            else: 
                entity_uri = entity_uri_list[0]
                res = SPARQL_data(entity_uri, abstract)
        # If you haven't been given property, fetch the abstract data of the most relevant entity
        else:
            entity_uri = entity_uri_list[0]
            res = SPARQL_data(entity_uri, abstract)
    # If you didn't find any entity URIs, return empty values
    else:
        entity_uri = ""
        res = []
    # Package the data and return it
    data = {'uri': entity_uri, 'result': res}
    json_data = json.dumps(data)
    return json_data