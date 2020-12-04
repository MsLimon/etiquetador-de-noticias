import os
import sys
import codecs
import csv
import json
import argparse
from itertools import groupby
from operator import itemgetter
from pattern.es import parsetree
from pattern.search import Pattern, search, taxonomy, TAXONOMY, STRICT, Word
# libraries for spacy version
import spacy
import es_core_news_md
import nltk
nltk.download('punkt')
import numpy as np

class ReporterExtractor(object):
    """ This class is in charge of parsing the sentences and extracting the
    sources, reporters and entities from the text.

    Resources are identified from those loaded in the taxonomy.

    Reporters and entities are extracted from those sentences where
    a reported speech verb is used. Whether a reporter is not clearly
    identified as the proper noun in the subject of the sentence, then
    see the list of entities as potential reporters.
    """

    __has_taxonomy = False  # to avoid load the taxonomy once and again

    def __init__(self):
        """ Initialize the extractor
        """
        # Create the taxonomy from files
        self._create_taxonomy()

        # List of words
        self.__sources, self.__reporters, self.__entities = [], [], []

        # Store the tree with the POS-Tagging, lemmata and gramatical relations
        self._tree = None

    def _create_taxonomy(self):
        """ Create a new taxonomy from the data files.
        """
#         location = os.path.dirname(os.path.realpath(sys.argv[0]))
        if not self.__has_taxonomy:
            self._add_category(file_name='data/reported_verbs.txt',
                               tag='RPTVRB')
            self._add_category(file_name='data/sources.txt',
                               tag='SOURCE')
            self._add_category(file_name='data/locations.txt',
                               tag='LOCATION')
            self.__has_taxonomy = True

    def _add_category(self, file_name, tag):
        """ Loads the terms into the taxonomy with the data from the specified
        file and assigns them the specified tag
        """
        with open(file_name) as f:
            for term in f:
                taxonomy.append(term.rstrip('\n'), type=tag)

    def _pack_list(self, data):
        """ Given a list of words as a tuples (string, index), it returns a
        new list containing only the string of the words. If words are
        consecutive in the text, they are concatenated.
        """
        return [' '.join([word.string for word in map(itemgetter(1), g)]) 
                for k, g in groupby(enumerate(data), lambda i_w: i_w[0]-i_w[1].index)]
    def _extract_sources(self):
        """ Extract those well-known sources from the text.
        """
        # search for well-known sources in the tree
        pattern = Pattern.fromstring('SOURCE', STRICT, taxonomy=TAXONOMY)

        for sentence in self.__tree:
            matches = pattern.search(sentence)

            for m in matches:
                for w in m.words:
                    self.__sources.append(w)

    def _is_composed_noun(self, word):
        """ Checks if a proper noun is composed:
        'Luís de Guindos', 'Ecologistas en Acción', etc.
        """
        return (word.previous() and word.previous().previous() and
                word.previous().string in ['de', 'en', 'del'] and
                #word.previous().tag in [u'IN'] and  # , u'NN', u'CC'] and
                word.previous().previous().tag == 'NNP')

    def _extract_reporters(self):
        """ Extract the reporters and entities from those sentence of the text
            where a reported speech verb is used.
        """
        # search for those sentences with reported speech verbs
        sentences = [s for s in self.__tree if search('RPTVRB|según', s)]
        # search for proper nouns that are not locations
        pattern = Pattern.fromstring('!LOCATION|NNP+',
                                     STRICT, taxonomy=TAXONOMY)

        for s in sentences:
            matches = pattern.search(s)

            for m in matches:
                for w in m.words:
                    # chunks with roles (SBJ, OBJ) connected to a reporter verb
                    if ((w.chunk.role is not None) and
                        (w.chunk.verb.head.lemma in taxonomy)):
                        if self._is_composed_noun(w):
                            self.__reporters.append(w.previous())
                        self.__reporters.append(w)
                    # proper nouns not spotlighted as reported
                    else:
                        if self._is_composed_noun(w):
                            self.__entities.append(w.previous())
                        self.__entities.append(w)

    def _clean(self, text):
        """ Performs some cleaning in the text
        """
        # some chars to remove
        for c in ['"', '\'', '”', '“', '¿', '?', '!', '¡']:
            text = text.replace(c, '')
        # some chars to replace by space
        for c in ['/', '─']:
            text = text.replace(c, ' ')

        return text

    def parse(self, text):
        """ Parses the text and extract the sources, reporters and entities.
        """
        self.__sources, self.__reporters, self.__entities = [], [], []
        text = self._clean(text)

        # POS-Tagging with relations and lemmas
        self.__tree = parsetree(text, relations=True, lemmata=True)

        # Extract the information
        self._extract_sources()
        self._extract_reporters()
        
    def remove_duplicates(self,name_list):
        """ Remove entities contained in others
        """
        new_name_list = []
        for w1 in name_list:
            repeated = False
            remain = set(name_list)-set([w1])
            for w2 in remain:
                if w1 in w2:
                    repeated = True
#                     print(f"{w1} está duplicado!")
            if not repeated:
                new_name_list.append(w1)
        new_name_list = list(set(new_name_list))
        # TODO - maybe only apply this to PER ent type and not to ORG type     
        return new_name_list

    def get_reporters(self):
        """Return reporters (list): the identified reporters
        """
        #self.reporters_out = self.__reporters
        self.reporters_out = self._pack_list(self.__reporters)
        self.reporters_out = self.remove_duplicates(self.reporters_out)
        return self.reporters_out

    def get_entities(self):
        """Return entities (list): the identified proper nouns
        """
        return list(set(self._pack_list(self.__entities))-
                    set(self._pack_list(self.__reporters)))

    def get_sources(self):
        """Return sources (list): the list of identified well-known sources
        """
        return self._pack_list(self.__sources)

class Entities(object):
    """This class manage the translation between usual names and their
    corresponding entities' full name.
    """

    def __init__(self):
#         location = os.path.dirname(os.path.realpath(sys.argv[0]))
        with open('data/entities.csv') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')
            self._entities_dict = {row['Entity'].lower():row
                                   for row in reader}

    def getFullName(self, name):
        if (name.lower() in list(self._entities_dict.keys()) and
            self._entities_dict[name.lower()]['FullName']):
                return self._entities_dict[name.lower()]['FullName']
        else:
            return name

    def getType(self, name):
        if name.lower() in list(self._entities_dict.keys()):
            return self._entities_dict[name.lower()]['Type']
        else:
            return None

    def getFullDescription(self, name):
        return {'name': name,
                'fullname': self.getFullName(name),
                'type':self.getType(name)}



# reload(sys)
# sys.setdefaultencoding('utf-8')


class SpacyReporterExtractor(object):
    """ This class is in charge of parsing the sentences and extracting the
    sources, reporters and entities from the text.

    Resources are identified from those loaded in the taxonomy.

    Reporters and entities are extracted from those sentences where
    a reported speech verb is used. Whether a reporter is not clearly
    identified as the proper noun in the subject of the sentence, then
    see the list of entities as potential reporters.
    """

    __has_taxonomy = False  # to avoid load the taxonomy once and again

    def __init__(self):
        """ Initialize the extractor
        """
        # Create the taxonomy from files
        self._create_taxonomy()

        # List of words
        self.__sources, self.__reporters, self.__entities = [], [], []

        # Store the tree with the POS-Tagging, lemmata and gramatical relations
        self._tree = None
        
        # load the language model for spacy
        self.nlp = es_core_news_md.load()
        
        # Set maximum character distance that we allow between the reported verb and the recognized entity to consider that it is a font        
        self._max_dist = 100
        
        
    def _create_taxonomy(self):
        """ Create a new taxonomy from the data files.
        """
#         location = os.path.dirname(os.path.realpath(sys.argv[0]))
        if not self.__has_taxonomy:
            self._add_category(file_name='data/reported_verbs.txt',
                               tag='RPTVRB')
            self._add_category(file_name='data/sources.txt',
                               tag='SOURCE')
            self._add_category(file_name='data/locations.txt',
                               tag='LOCATION')
            self.__has_taxonomy = True

    def _add_category(self, file_name, tag):
        """ Loads the terms into the taxonomy with the data from the specified
        file and assigns them the specified tag
        """
        with open(file_name) as f:
            for term in f:
                taxonomy.append(term.rstrip('\n'), type=tag)

    def _pack_list(self, data):
        """ Given a list of words as a tuples (string, index), it returns a
        new list containing only the string of the words. If words are
        consecutive in the text, they are concatenated.
        """
        return [' '.join([word.string for word in map(itemgetter(1), g)]) 
                for k, g in groupby(enumerate(data), lambda i_w: i_w[0]-i_w[1].index)]
    def _extract_sources(self):
        """ Extract those well-known sources from the text.
        """
        # search for well-known sources in the tree
        pattern = Pattern.fromstring('SOURCE', STRICT, taxonomy=TAXONOMY)

        for sentence in self.__tree:
            matches = pattern.search(sentence)

            for m in matches:
                for w in m.words:
                    self.__sources.append(w)
    
    
    def _get_distance(self,w1, w2, txt):
        pos_w1 = txt.find(w1)
        pos_w2 = txt.find(w2)
        return pos_w2 - pos_w1

    def _extract_reporters(self):
        """ Extract the reporters and entities from those sentence of the text
            where a reported speech verb is used.
        """
        # search for those sentences with reported speech verbs
        sentences = [s for s in self.__tree if search('RPTVRB|según', s)]

        for s in sentences:
            s_str = s.string
            sent_nlp = self.nlp(s_str)
            text = s_str
            
            verb = search('RPTVRB|según',s)[0].string
            shortest_dist = np.inf
            shortest_word = []
            for ent in sent_nlp.ents:
                # calculate distance
                dist = self._get_distance(verb, ent.text, s_str)
                # store all proper nouns in entities
                word = Word(s, ent.text, tag=None, index=s.id)
                self.__entities.append(word)
                # PER and ORG type entities closest to a reporter verb
                if ent.label_ in ["PER","ORG"] and abs(dist) < shortest_dist:
                    word = Word(s, ent.text, tag='NNP', index=s.id)
                    shortest_dist = abs(dist)
                    shortest_word = word
            if shortest_word and abs(dist) < self._max_dist:
                self.__reporters.append(shortest_word)


    def _clean(self, text):
        """ Performs some cleaning in the text
        """
        # some chars to remove
        for c in ['"', '\'', '”', '“', '¿', '?', '!', '¡']:
            text = text.replace(c, '')
        # some chars to replace by space
        for c in ['/', '─']:
            text = text.replace(c, ' ')

        return text

    def parse(self, text):
        """ Parses the text and extract the sources, reporters and entities.
        """
        self.__sources, self.__reporters, self.__entities = [], [], []
        text = self._clean(text)

        # POS-Tagging with relations and lemmas
        self.__tree = parsetree(text, relations=True, lemmata=True)

        # Extract the information
        self._extract_sources()
        self._extract_reporters()
        
    def remove_duplicates(self,name_list):
        """ Remove entities contained in others
        """
        new_name_list = []
        for w1 in name_list:
            repeated = False
            remain = set(name_list)-set([w1])
            for w2 in remain:
                if w1 in w2:
                    repeated = True
#                     print(f"{w1} está duplicado!")
            if not repeated:
                new_name_list.append(w1)
        new_name_list = list(set(new_name_list))
        # TODO - maybe only apply this to PER ent type and not to ORG type     
        return new_name_list
        

    def get_reporters(self):
        """Return reporters (list): the identified reporters
        """
        self.reporters_out = [w.string for w in self.__reporters]
        self.reporters_out = self.remove_duplicates(self.reporters_out)
        
        return self.reporters_out

    def get_entities(self):
        """Return entities (list): the identified proper nouns
        """
        self.entities_out = [w.string for w in self.__entities]
        return list(set(self.entities_out)-
                    set(self.reporters_out))

    def get_sources(self):
        """Return sources (list): the list of identified well-known sources
        """
        return self._pack_list(self.__sources)

class Entities(object):
    """This class manage the translation between usual names and their
    corresponding entities' full name.
    """

    def __init__(self):
#         location = os.path.dirname(os.path.realpath(sys.argv[0]))
        with open('data/entities.csv') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',')
            self._entities_dict = {row['Entity'].lower():row
                                   for row in reader}

    def getFullName(self, name):
        if (name.lower() in list(self._entities_dict.keys()) and
            self._entities_dict[name.lower()]['FullName']):
                return self._entities_dict[name.lower()]['FullName']
        else:
            return name

    def getType(self, name):
        if name.lower() in list(self._entities_dict.keys()):
            return self._entities_dict[name.lower()]['Type']
        else:
            return None

    def getFullDescription(self, name):
        return {'name': name,
                'fullname': self.getFullName(name),
                'type':self.getType(name)}