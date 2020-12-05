import os
import spacy
from spacy import displacy
from collections import Counter
import es_core_news_md
import nltk
nltk.download('punkt')
from newspaper import Article
import pkg_resources
import pandas as pd
import numpy as np
import re
from bs4 import BeautifulSoup
from etiquetador_noticias.tjtool import ReporterExtractor, SpacyReporterExtractor, Entities

this_dir, this_filename = os.path.split(__file__)

class Analyser():
    """Auditor de transparencia informativa en medios digitales


    Parameters
    ----------
    url : str
        The url to the article to be analysed and labelled
    variant : str, optional
        The variant of the tree used to classify the article. Allowed values are "seria" or "gamberra" (default is "seria")
    Returns
    -------
    Full report in text form
        
    Examples
    --------
    >>> from etiquetador_noticias.analyser import Analyser
    >>> url = "https://www.article_url"
    >>> Analyser(url)
    """
    __has_data = False # to avoid load the data once and again
    def __init__(self, url, variant="seria"):
        # inputs
        self.url = url
        if not isinstance(variant, str):
            raise TypeError("""The parameter 'variant' of the tree must be a string containing 
                the name of the  desired variant. Allowed values are "seria" or "gamberra".""")
        self.variant = variant
        # load spanish model
        self._nlp = es_core_news_md.load()
        # load data
        self._load_data()
        
        # initalize article
        self.article = Article(self.url)
        # download and parse article
        self.article.download()
        self.article.parse()
        # store basic info
        self.text = self.article.text
        self.source_url = self.article.source_url
        if self.source_url in self.df_url_media.media_url.tolist():
            self.recognized_media = True
        else:
            self.recognized_media = False
            
        if self.recognized_media:
            self.media_name = self.df_url_media.loc[self.df_url_media.media_url==self.source_url,'media_name'].iloc[0]
        else:
            self.media_name = self.source_url

            
    def _load_data(self):
        """Cargar los datos necesarios.
        """
        if not self.__has_data:
            table_file = os.path.join(this_dir, "data", "tabla_de_inversores_y_grandes_anunciantes.xlsx")
            self.df_fin = pd.read_excel(table_file)
            self.df_url_media = self.df_fin[["media_name","media_url"]].drop_duplicates()
            self.__has_data = True

        
    def detect_banners(self):
        """Detectar si el articulo es explicitamente publicitario.
        """
        if self.media_name=="EL PAÍS":
            soup = BeautifulSoup(self.article.html, 'html5lib')
            self.pat_list = []
            try:
                res = soup.find_all('a',{"class","badge_link"})[0]
                detected_text = self._nlp(res.get_text(separator=" "))
                self.pat_list = [ent for ent in detected_text.ents]
                self.pat = True
                self.pat_out_msg = f"\n- Hemos detectado que este es un articulo patrocinado por {detected_text.ents[0]}\n"
            except:
                self.pat = False
                self.pat_out_msg = "\n- No hemos detectado patrocinio explicito\n"
        else:
            self.pat = False
            self.pat_out_msg = f"\n- De momento no tenemos un método para detectar patrocinio explicito en el medio {self.source_url} :(\n"
            
    def detect_reporters(self):
        """Detectar fuentes utilizando la herramienta de TJTool.
        """
        extractor = ReporterExtractor()
        translate = Entities()
        extractor.parse(self.article.text)
        self.reporters = extractor.get_reporters()
        self.entities = extractor.get_entities()
        self.sources = extractor.get_sources()
        
        fd = lambda x: translate.getFullDescription(x)
        self.reporters_plus = list(map(fd, extractor.get_reporters()))
        self.entities_plus = list(map(fd, extractor.get_entities()))
        self.sources_plus = list(map(fd, extractor.get_sources()))
        # count reporters and sources
        self.num_reporters = len(self.reporters)
        self.num_sources = len(self.sources)
        self.total_sources = self.reporters + self.sources
        self.num_total_sources = self.num_reporters + self.num_sources
        
        self.reporters_out_msg = f"- Hemos encontrado {self.num_total_sources} fuente(s) en el artículo:\n"

        
    def detect_publi_in_text(self):
        """Detectar si el articulo habla sobre uno de los grandes patrocinadores o inversores del medio.
        """
        self.pub_text = False
        if self.recognized_media:
            # select pat_entitites related to media
            df_fin_media = self.df_fin[self.df_fin.media_url==self.source_url]            
            self.detected_pat = []
            # check if the pat_entity is contained in the article
            for ele in df_fin_media.pat_entity.tolist():
                if ele in self.article.text:
                    pat_type = df_fin_media[df_fin_media.pat_entity==ele].pat_type.iloc[0]
                    self.pub_text_out_msg = f"\n- Hemos detectado que este articulo habla sobre {ele}, que es un {pat_type} de {self.media_name}\n"
                    self.detected_pat.append(ele)
                    self.pub_text = True
            if not self.detected_pat: 
                self.pub_text_out_msg = f"\n- No hemos detectado que este articulo hable sobre algún gran anunciante o inversor de {self.media_name}\n"
                    
            return self.detected_pat
        else:
            self.pub_text_out_msg = f"\n- De momento no tenemos información sobre los financiadores del medio {self.source_url} :(\n"
            

    def get_category(self):
        # si tiene publicidad explicita es publicidad
        if self.pat:
            # si tiene un indicador de patrocinio y contiene publicidad en el texto es publicidad
            if self.pub_text:
                self.category = "Publicidad"
            # si tiene un indicador de patrocinio y no contiene publicidad en el texto es contenido patrocinado
            else:
                self.category = "Contenido Patrocinado"
        # si no tiene publicidad explicita....
        else:
            if self.num_total_sources > 2:
                # si tiene más de dos fuentes pero habla de un inversor o gran anunciante es publicidad encubierta
                if self.pub_text:
                    self.category = "Publicidad Encubierta"
                # si tiene más de dos fuentes pero NO habla de un inversor o gran anunciante es información
                else:
                    self.category = "Información"
            else:
                # si tiene menos de dos fuentes pero habla de un inversor o gran anunciante es publicidad encubierta
                if self.pub_text:
                    self.category = "Publicidad Encubierta"
                # si tiene menos de dos fuentes pero NO habla de un inversor o gran anunciante es contenido parcial
                else:
                    self.category = "Contenido Parcial"
                    
        return self.category
                
#     def get_category(self):
#         # si tiene publicidad explicita es publicidad
#         if self.pat:
#             self.category = "Publicidad"
#         # si no tiene publicidad explicita....
#         else:
#             if self.num_total_sources > 2:
#                 # si tiene más de dos fuentes pero habla de un inversor o gran anunciante es publicidad encubierta
#                 if self.pub_text:
#                     self.category = "Publicidad Encubierta"
#                 # si tiene más de dos fuentes pero NO habla de un inversor o gran anunciante es información
#                 else:
#                     self.category = "Información"
#             else:
#                 # si tiene menos de dos fuentes pero habla de un inversor o gran anunciante es publicidad encubierta
#                 if self.pub_text:
#                     self.category = "Publicidad Encubierta"
#                 # si tiene menos de dos fuentes pero NO habla de un inversor o gran anunciante es contenido parcial
#                 else:
#                     self.category = "Contenido Parcial"
                    
#         return self.category
                
    
    
    def full_report(self):
        print("------------------------FULL REPORT---------------------\n")
        date = self.article.publish_date.strftime("%d-%m-%Y %H:%M:%S")
        print(f"Fecha de publicación: {date}\n")
        print(f"Autores:")
        print(self.article.authors)
        print("\n------------------\n")
        self.detect_banners()
        print(self.pat_out_msg)
        self.detect_reporters()
        print(self.reporters_out_msg)
        print(self.total_sources)
        self.detect_publi_in_text()
        print(self.pub_text_out_msg)
        print("------------------\n")
        self.get_category()
        print(f"\nEl artículo ha sido clasificado como {self.category}\n")