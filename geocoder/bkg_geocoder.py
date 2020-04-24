import requests
import re

from geocoder.geocoder import Geocoder

URL = 'http://sg.geodatenzentrum.de/gdz_geokodierung__{key}/geosearch'


class BKGGeocoder(Geocoder):
    '''
    Geocoder using the BKG API
    '''
    # API keywords (label/key pairs)
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

    @staticmethod
    def split_code_city(value):
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

    # special keywords are keywords that are not supported by API but
    # its values are to be further processed into seperate keywords
    special_kw = {
        'plz_ort': split_code_city,
    }

    def __init__(self, key='', url='', srs: str='EPSG:4326', logic_link='AND',
                 rs='', fuzzy=False, area_wkt=None):
        if not key and not url:
            raise ValueError('at least one keyword out of "key" and "url" has '
                             'to be passed')
        url = url or self.get_url(key)
        self.logic_link = logic_link
        self.fuzzy = fuzzy
        self.rs = rs
        self.area_wkt = area_wkt
        super().__init__(url=url, srs=srs)

    @staticmethod
    def get_url(key):
        return URL.format(key=key)

    def _build_params(self, *args, **kwargs):
        suffix = '~' if self.fuzzy else ''
        logic = f' {self.logic_link} '
        query = logic.join([f'{a}{suffix}' for a in args if a]) or ''
        if args and kwargs:
            query += logic
        # pop and process the special keywords
        special = [k for k in kwargs.keys() if k in self.special_kw]
        for k in special:
            value = kwargs.pop(k)
            kwargs.update(self.special_kw[k].__func__(value))
        query += logic.join((f'{k}:({v}){suffix}' for k, v in kwargs.items()
                             if v))
        if self.rs:
            query = f'({query}) AND rs:{self.rs}'
        return query

    def query(self, *args, **kwargs):
        self.params = {}
        if self.area_wkt:
            self.params['geometry'] = self.area_wkt
        self.params['srsname'] = self.srs
        query = self._build_params(*args, **kwargs)
        if not query:
            raise Exception('keine Suchparameter gefunden')
        self.params['query'] = query
        self.r = requests.get(self.url, params=self.params)
        # ToDo raise specific errors
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        return self.r.json()['features']

    def reverse(self, x, y):
        params = {
            'lat': y,
            'lon': x,
            'srsname': self.srs
        }
        self.r = requests.get(self.url, params=params)
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        return self.r.json()['features']


