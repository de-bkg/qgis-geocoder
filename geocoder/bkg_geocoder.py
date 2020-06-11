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

import requests
import re

from geocoder.geocoder import Geocoder

# default url to the BKG geocoding service, key has to be replaced
URL = 'http://sg.geodatenzentrum.de/gdz_geokodierung__{key}/geosearch'


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
        'ortsteil': 'Ortsteil'
    }
    special_characters = ['+', '&&', '||', '!', '(', ')', '{', '}',
                          '[', ']', '^', '"', '~', '*', '?', ':']

    @staticmethod
    def split_code_city(value: str) -> dict:
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

    special_keywords = {
        'plz_ort': split_code_city,
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
            complete service-url provided by BKG (no seperate key needed)
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
        return URL.format(key=key)

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
            kwargs.update(self.special_keywords[k].__func__(value))
        query += logic.join((f'{k}:({self._escape_special_chars(v)}){suffix}'
                             for k, v in kwargs.items() if v))
        if self.rs:
            query = f'({query}) AND rs:{self.rs}'
        return query

    def query(self, *args: object, **kwargs: object) -> dict:
        '''
        query

        Parameters
        ----------
        *args
            query parameters without keyword
        **kwargs
            query parameters with keyword and value

        Returns
        ----------
        dict
            list of geojson features with "geometry" attribute as the geocoding
            result and "properties" containing "text" (description of found
            address in BKG database),"typ", "treffer" and "score" (the higher
            the better the match)

        Raises
        ----------
        Exception
            API responds with a status code different from 200 (OK) or no
            search terms are given
        '''
        self.params = {}
        if self.area_wkt:
            self.params['geometry'] = self.area_wkt
        self.params['srsname'] = self.crs
        query = self._build_params(*args, **kwargs)
        if not query:
            raise Exception('keine Suchparameter gefunden')
        self.params['query'] = query
        self.r = requests.get(self.url, params=self.params)
        # ToDo raise specific errors
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        return self.r.json()['features']

    def reverse(self, x: float, y: float) -> list:
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
        list
            list of geojson features with "geometry" attribute of the matched
            address "properties" containing "text" attribute (description of
            the found address) in order of distance to queried point

        Raises
        ----------
        Exception
            API responds with a status code different from 200 (OK)
        '''
        params = {
            'lat': y,
            'lon': x,
            'srsname': self.crs
        }
        self.r = requests.get(self.url, params=params)
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        return self.r.json()['features']


