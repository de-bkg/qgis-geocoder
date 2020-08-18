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

from typing import List, Tuple
import re
from html.parser import HTMLParser
from json.decoder import JSONDecodeError

from .geocoder import Geocoder
from bkggeocoder.interface.utils import Request, Reply

requests = Request()

# default url to the BKG geocoding service, key has to be replaced
URL = 'http://sg.geodatenzentrum.de/gdz_geokodierung__{key}'


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
            fuzzy search, the terms don't have to match exactly if set True,
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
    def get_crs(url: str = '', key: str = '') -> Tuple[bool, List[tuple]]:
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
            tuple of success and list of available crs as tuples (code,
            pretty name)
        '''
        url = url or URL.format(key=key)
        # in case users typed in url with the 'geosearch' term in it
        url = url.replace('geosearch', '')
        url += '/index.xml'
        try:
            res = requests.get(url)
            parser = CRSParser()
            parser.feed(res.content.decode("utf-8"))
        except ConnectionError:
            return False, [('EPSG:25832', 'ETRS89 / UTM zone 32N')]
        return True, parser.codes

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
        return text

    def _build_params(self, *args: object, **kwargs: object) -> str:
        '''builds a query string from given parameters'''
        suffix = '~' if self.fuzzy else ''
        logic = f' {self.logic_link} '
        query = logic.join([f'"{self._escape_special_chars(a)}"{suffix}'
                            for a in args if a]) or ''
        if args and kwargs:
            query += logic
        # pop and process the special keywords
        special = [k for k in kwargs.keys() if k in self.special_keywords]
        for k in special:
            value = kwargs.pop(k)
            kwargs.update(self.special_keywords[k].__func__(value, kwargs))
        query += logic.join((f'{k}:({self._escape_special_chars(v)}){suffix}'
                             for k, v in kwargs.items() if v))
        if self.rs:
            query = f'({query}) AND rs:{self.rs}'
        return query

    def query(self, *args: object, **kwargs: object) -> Reply:
        '''
        query the service

        Parameters
        ----------
        *args
            query parameters without keyword
        **kwargs
            query parameters with keyword and value

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
        if self.area_wkt:
            self.params['geometry'] = self.area_wkt
        self.params['srsname'] = self.crs
        query = self._build_params(*args, **kwargs)
        if not query:
            raise RuntimeError('keine Suchparameter gefunden')
        self.params['query'] = query
        self.reply = requests.get(self.url, params=self.params)
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
            raise ValueError('interner Serverfehler')
        if reply.status_code == None:
            raise RuntimeError('Service nicht erreichbar')
        if reply.status_code == 404:
            raise ValueError(f'Die Seite {reply.url[:30] + "..."} '
                             'ist nicht erreichbar.')
        if reply.status_code != 200:
            raise ValueError(f'{reply.status_code} unbekannter Fehler')

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


