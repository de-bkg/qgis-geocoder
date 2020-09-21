# -*- coding: utf-8 -*-
'''
***************************************************************************
    bkg_geocoder.py
    ---------------------
    Date                 : March 2020
    Author               : Christoph Franke
    Copyright            : (C) 2020 by Bundesamt für Kartographie und Geodäsie
    Email                : franke at ggr-planung dot de
***************************************************************************
*                                                                         *
*   This program is free software: you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 3 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************

implementation of the generic geocoding interface to work with the BKG
geocoding API
'''

__author__ = 'Christoph Franke'
__date__ = '16/03/2020'
__copyright__ = 'Copyright 2020, Bundesamt für Kartographie und Geodäsie'

from typing import List, Tuple, Union
import re
from qgis.PyQt.QtCore import QUrlQuery, QUrl
from html.parser import HTMLParser
from json.decoder import JSONDecodeError

from .geocoder import Geocoder
from bkggeocoder.interface.utils import Request, Reply, ResField

requests = Request()

# default url to the BKG geocoding service, key has to be replaced
URL = 'http://sg.geodatenzentrum.de/gdz_geokodierung__{key}'

# fields added to the input layer containing the properties of the results
prefix = 'bkg'

# ['text', 'typ', 'score', 'bbox', 'ags', 'rs', 'schluessel', 'bundesland', 'regbezirk', 'kreis', 'verwgem', 'gemeinde', 'plz', 'ort', 'ortsteil', 'strasse', 'haus', 'qualitaet', 'treffer']
BKG_RESULT_FIELDS = [
    # required by UI
    ResField('typ', 'text', alias='Klassifizierung', prefix=prefix),
    ResField('text', 'text',  alias='Anschrift laut Dienst', prefix=prefix),
    ResField('score', 'float8', alias='Score', prefix=prefix),
    ResField('treffer', 'text', alias='Trefferbewertung', prefix=prefix),
    # optional fields
    ResField('qualitaet', 'text', alias='Qualität', prefix=prefix,
             optional=True),
    ResField('ags', 'text', alias='AGS laut Dienst', prefix=prefix,
             optional=True),
    ResField('rs', 'text', alias='RS laut Dienst', prefix=prefix,
             optional=True),
    ResField('schluessel', 'text', alias='Schlüssel laut Dienst',
             prefix=prefix, optional=True),
    ResField('bundesland', 'text', alias='Bundesland laut Dienst',
             prefix=prefix, optional=True),
    ResField('regbezirk', 'text', alias='Regierungsbezirk laut Dienst',
             prefix=prefix, optional=True),
    ResField('kreis', 'text', alias='Kreis laut Dienst',
             prefix=prefix, optional=True),
    ResField('verwgem', 'text', alias='Verwaltungsgemeinde laut Dienst',
             prefix=prefix, optional=True),
    ResField('gemeinde', 'text', alias='Gemeinde laut Dienst',
             prefix=prefix, optional=True),
    ResField('plz', 'text', alias='Posleitzahl laut Dienst',
             prefix=prefix, optional=True),
    ResField('ort', 'text', alias='Ort laut Dienst',
             prefix=prefix, optional=True),
    ResField('ortsteil', 'text', alias='Ortsteil laut Dienst',
             prefix=prefix, optional=True),
    ResField('strasse', 'text', alias='Strasse laut Dienst',
             prefix=prefix, optional=True),
    ResField('haus', 'text', alias='Hausnummer laut Dienst',
             prefix=prefix, optional=True)
]

# "Regionalschlüssel" to filter "Bundesländer"
RS_PRESETS = [
    ('Schleswig-Holstein', '01*'),
    ('Freie und Hansestadt Hamburg', '02*'),
    ('Niedersachsen', '03*'),
    ('Freie Hansestadt Bremen', '04*'),
    ('Nordrhein-Westfalen', '05*'),
    ('Hessen', '06*'),
    ('Rheinland-Pfalz', '07*'),
    ('Baden-Württemberg', '08*'),
    ('Freistaat Bayern', '09*'),
    ('Saarland', '10*'),
    ('Berlin', '11*'),
    ('Brandenburg', '12*'),
    ('Mecklenburg-Vorpommern', '13*'),
    ('Freistaat Sachsen', '14*'),
    ('Sachsen-Anhalt', '15*'),
    ('Freistaat Thüringen', '16*')
]

class ErrorCodeParser(HTMLParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error = None

    def handle_starttag(self, tag, attrs):
        if tag == 'serviceexception':
            attrs = dict(attrs)
            self.error = attrs.get('code')
            return


class CRSParser(HTMLParser):
    '''
    parse OpenSearch description of BKG geocoding api to find supported
    coordinate reference systems

    HTMLParser is used for compatibility reasons to 3.4 (no lxml included)

    Attributes
    ----------
    codes : list
        list of available crs as tuples (code, pretty name), filled while
        feeding the desctiption xml to this parser
    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.codes = []

    def handle_starttag(self, tag, attrs):
        '''
        override, append tags describing a supported crs to the codes list
        '''
        if tag.startswith('query'):
            attrs = dict(attrs)
            if 'bkg:srsname' in attrs:
                self.codes.append((attrs['bkg:srsname'], attrs['title']))

    def clean(self):
        '''
        reset the parser
        '''
        self.codes = []


class BKGGeocoder(Geocoder):
    '''
    Geocoder using the BKG API. The geocoder requires either a key or a
    service-url provided by the "Bundesamt für Kartographie und Geodäsie" to
    work

    Attributes
    ----------
    keywords : dict
        search paramaters of the API as keys and pretty names as values
    special_keywords : dict
        keywords that are not directly supported by the API but
        can be used by splitting the input into seperate supported keywords
    special_characters : list
        control characters that should be escaped if not used as such
    exception_codes : dict
        possible error codes returned by the API on error and the translated
        messages
    '''

    keywords = {
        'ort': 'Ort',
        'ortsteil': 'Ortsteil',
        'strasse': 'Straße',
        'haus': 'Hausnummer',
        'plz': 'Postleitzahl',
        'strasse_haus': 'Straße + Hausnummer',
        'plz_ort': 'Postleitzahl + Ort',
        'gemeinde': 'Gemeinde',
        'kreis': 'Kreis',
        'verwgem': 'Verwaltungsgemeinde',
        'bundesland': 'Bundesland',
        'ortsteil': 'Ortsteil',
        'zusatz': 'Zusatz (zu Hausnummer)'
    }

    exception_codes = {
        'ERROR_UNKNOWN_IDENT': ('Falsche UUID oder fehlende Zugriffsrechte auf '
                                'den Geokodierungsdienst'),
        'ERROR_UNKNOWN_SERVICE': 'Unbekannter Service',
        'NOACCESS_SERVICE': 'Kein Zugriff',
        'MissingParameterValue': 'Fehlende Parameter',
        'InvalidParameterValue': 'Ungültiger Parameterwert'
    }

    special_characters = ['+', '&&', '||', '!', '(', ')', '{', '}',
                          '[', ']', '^', '"', '~', '*', '?', ':']
    fuzzy_distance = 0.5

    @staticmethod
    def split_code_city(value: str, kwargs: dict) -> dict:
        '''extract zip-code and city from a string'''
        res = {}
        # all letters and '-', rejoin them with spaces
        re_city = '([a-zA-ZäöüßÄÖÜ\-]+)'
        f = re.findall(re_city, value)
        if f:
            res['ort'] = ' '.join(f)
        re_code = '([0-9]{5})'
        f = re.findall(re_code, value)
        if f:
            res['plz'] = f[0]
        return res

    @staticmethod
    def join_number(value: str, kwargs: dict) -> dict:
        '''
        join house number and addition
        warning: changes kwargs in place
        '''
        nr = kwargs.pop('haus', '')
        return {'haus': f'{nr}{value}'}

    special_keywords = {
        'plz_ort': split_code_city,
        'zusatz': join_number
    }

    @staticmethod
    def fill_post_code(value: Union[str, int], kwargs: dict) -> dict:
        '''
        fill up post codes shorter than 5 characters with leading zeros
        '''
        return {'plz': str(value).zfill(5)}

    special_keywords = {
        'plz_ort': split_code_city,
        'zusatz': join_number,
        'plz': fill_post_code
    }

    def __init__(self, key: str = '', url: str = '', crs: str = 'EPSG:4326',
                 logic_link = 'AND', rs: str = '', fuzzy: bool = False,
                 area_wkt: str = None):
        '''
        Parameters
        ----------
        key : str, optional
            key provided by BKG (no url needed, url will be built with that)
        url : str, optional
            complete service-url provided by BKG (no seperate key needed),
            higher priority than the key if both are given
        crs : str, optional
            code of projection the returned geometries will be in,
            defaults to epsg 4326
        logic_link : str, optional
            logic link of the search terms, defaults to AND
            AND - all search terms have to match
            OR - one search term has to match
        rs : str, optional
            "Regionalschlüssel", restrict results to be in region matching this
            key, defaults to no restriction
        area_wkt : str, optional
            wkt text describing a (multi-)polygon, restrict results to be in
            this area, defaults to no restriction
        fuzzy : bool, optional
            fuzzy search, the terms don't have to match exactly if set to True,
            defaults to not using fuzzy search
        '''
        if not key and not url:
            raise ValueError('at least one keyword out of "key" and "url" has '
                             'to be passed')
        url = url or self.get_url(key)
        # users already might typed in url with 'geosearch' term in it
        if 'geosearch' not in url:
            url += '/geosearch'
        self.logic_link = logic_link
        self.fuzzy = fuzzy
        self.rs = rs
        self.area_wkt = area_wkt
        super().__init__(url=url, crs=crs)

    @staticmethod
    def get_url(key: str) -> str:
        '''
        create a service-url for the given key

        Parameters
        ----------
        key : str
            key provided by BKG for using the geocoding service

        Returns
        ----------
        str
            service url corresponding to given key
        '''
        url = URL.format(key=key)
        return url

    @staticmethod
    def get_crs(url: str = '', key: str = '') -> Tuple[bool, str, List[tuple]]:
        '''
        request the supported coordinate reference sytems

        Parameters
        ----------
        key : str, optional
            key provided by BKG (no url needed, url will be built with that)
        url : str, optional
            complete service-url provided by BKG (no seperate key needed),
            higher priority than the key if both are given

        Returns
        ----------
        tuple
            tuple of success, error message and list of available crs as tuples
            (code, pretty name)
        '''
        url = url or URL.format(key=key)
        # in case users typed in url with the 'geosearch' term in it
        url = url.replace('geosearch', '')
        url += '/index.xml'
        default = [('EPSG:25832', 'ETRS89 / UTM zone 32N')]
        con_msg = 'Der Dienst ist zur Zeit nicht erreichbar.'
        try:
            res = requests.get(url)
        except ConnectionError:
            return False, con_msg, default
        if res.status_code == None:
            return False, con_msg, default
        if res.status_code != 200:
            msg = 'Der eingegebene Schlüssel bzw. die URL ist nicht gültig'
            return False, msg, default
        parser = CRSParser()
        parser.feed(res.content.decode("utf-8"))
        return True, '', parser.codes

    def _escape_special_chars(self, text) -> str:
        '''
        escapes control characters in given string

        Parameters
        ----------
        text : str
            text

        Returns
        ----------
        str
            text with escaped control characters
        '''
        for char in self.special_characters:
            text = text.replace(char, r'\{}'.format(char))
        return text.rstrip().lstrip()

    def _add_fuzzy(self, text: str) -> str:
        '''decorate text with fuzzy operators'''
        if not self.fuzzy or not text:
            return text
        terms = text.rstrip().lstrip().split(' ')
        operator = f'~{self.fuzzy_distance} '
        fuzzy = operator.join(terms) + operator
        return fuzzy.rstrip()

    def _build_params(self, *args: object, **kwargs: object) -> str:
        '''builds a query string from given parameters'''
        logic = f' {self.logic_link} '
        p_args = [self._add_fuzzy(self._escape_special_chars(str(a)))
                  for a in args]
        query = logic.join([f'"{a}"' for a in p_args if a]) or ''
        if args and kwargs:
            query += logic
        # pop and process the special keywords
        special = [k for k in kwargs.keys() if k in self.special_keywords]
        for k in special:
            value = kwargs.pop(k)
            kwargs.update(self.special_keywords[k].__func__(value, kwargs))
        p_kwargs = {k: self._add_fuzzy(self._escape_special_chars(v))
                    for k, v in kwargs.items()}
        query += logic.join((f'{k}:({v})' for k, v in p_kwargs.items() if v))
        return query

    def query(self, *args: object, max_retries: int = 2, **kwargs: object
              ) -> Reply:
        '''
        query the service

        Parameters
        ----------
        *args
            query parameters without keyword
        **kwargs
            query parameters with keyword and value
        max_retries: int, optional
            maximum number of retries after connection error, defaults to 2
            retries

        Returns
        ----------
        Reply
            the reply of the geocoding API, contains a list of geojson features
            with "geometry" attribute of the matched address "properties"
            containing "text" (description of found address in BKG database),
            "typ", "treffer" and "score" (the higher the better the match)

        Raises
        ----------
        RuntimeError
            critical error (no parameters, no access to service/url),
            it is recommended to abort geocoding
        ValueError
            request got through but parameters were malformed,
            may still work for different features
        '''
        self.params = {}
        retries = 0
        if self.rs:
            self.params['filter'] = f'rs:{self.rs}'
        self.params['srsname'] = self.crs
        query = self._build_params(*args, **kwargs)
        if not query:
            raise ValueError('keine Suchparameter gefunden')
        self.params['query'] = query
        do_post = self.area_wkt is not None
        if self.area_wkt:
            self.params['geometry'] = self.area_wkt
        while True:
            try:
                if not do_post:
                    self.reply = requests.get(self.url, params=self.params)
                else:
                    content_type = 'application/x-www-form-urlencoded'
                    data = QUrlQuery()
                    for k, v in self.params.items():
                        data.addQueryItem(k, v)
                    self.reply = requests.post(
                        self.url, data=data.query().encode('utf-8'),
                        content_type=content_type
                    )
            except ConnectionError:
                if retries >= max_retries:
                    raise RuntimeError(
                        f'Anfrage nach {retries + 1} gescheiterten '
                        'Verbindungsversuchen abgebrochen.')
                retries += 1
                continue
            break
        self.raise_on_error(self.reply)
        return self.reply

    def raise_on_error(self, reply: Reply):
        '''
        raise errors if reply is not valid
        (valid only with HTML status code 200)

        Parameters
        ----------
        reply : Reply
            BKG service reply

        Raises
        ----------
        RuntimeError
            no access to service/url
        ValueError
            malformed request parameters
        '''
        # depending on error json or xml is returned from API
        if reply.status_code == 400:
            # json response if parameters were malformed
            try:
                res_json = reply.json()
                code = res_json.get('exceptionCode')
                message = self.exception_codes.get(code)
                raise ValueError(message)
            # xml response if service could not be accessed
            except JSONDecodeError:
                parser = ErrorCodeParser()
                parser.feed(reply.content.decode('utf-8'))
                message = self.exception_codes.get(parser.error)
                raise RuntimeError(message)
        if reply.status_code == 500:
            raise ValueError('500 - interner Serverfehler')
        if reply.status_code == None:
            raise RuntimeError(f'Service "{reply.url[:30] + "..."}" nicht '
                               'erreichbar. Bitte überprüfen Sie die '
                               'eingegebene Dienst-URL und ihre '
                               'Internetverbindung.')
        if reply.status_code == 404:
            raise ValueError(
                f'404 - "{reply.url[:30] + "..."}" nicht gefunden.')
        if reply.status_code != 200:
            raise ValueError(f'{reply.status_code} - unbekannter Fehler')

    def reverse(self, x: float, y: float) -> Reply:
        '''
        query

        Parameters
        ----------
        x : int
            x coordinate (longitude)
        y : float
            y coordinate (latitude)

        Returns
        ----------
        Reply
            the reply of the geocoding API, contains a list of geojson features
            with "geometry" attribute of the matched address "properties"
            containing "text" attribute (description of the found address)
            in order of distance to queried point

        Raises
        ----------
        RuntimeError
            no access to service/url
        ValueError
            malformed request parameters
        '''
        params = {
            'lat': y,
            'lon': x,
            'srsname': self.crs
        }
        self.reply = requests.get(self.url, params=params)
        self.raise_on_error(self.reply)
        return self.reply


