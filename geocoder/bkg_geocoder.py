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
        'strasse_hnr': 'Straße + Hausnummer',
        'plz_ort': 'Postleitzahl + Ort',
    }

    @staticmethod
    def split_street_nr(value):
        res = {}
        # finds the last number with max. one trailing letter in the string
        # (and possible spaces in between)
        re_nr = '([\s\-]+[0-9]+[\s]*[a-zA-Z]{0,1}[\s]*$)'
        f = re.findall(re_nr, value)
        if f:
            # take the last number found (e.g. bkg doesn't understand '6-8')
            res['haus'] = f[-1].replace('-', '').replace(' ', '')
        re_street = '([a-zA-ZäöüßÄÖÜ\\s\-\.]+[0-9]*[.\\]*[a-zA-ZäöüßÄÖÜ]+)'
        m = re.match(re_street, value)
        if m:
            res['strasse'] = m[0]
        return res

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
        'strasse_hnr': split_street_nr,
        'plz_ort': split_code_city,
    }

    def __init__(self, key, srs: str='EPSG:4326', logic_link='AND', rs='',
                 fuzzy=False):
        url = URL.format(key=key)
        self.logic_link = logic_link
        self.fuzzy = fuzzy
        self.rs = rs
        super().__init__(url=url, srs=srs)

    def _build_params(self, args, kwargs):
        suffix = '~' if self.fuzzy else ''
        logic = ' {} '.format(self.logic_link)
        query = logic.join(
            ['{a}{s}'.format(a=a, s=suffix) for a in args if a]
            ) or ''
        if args and kwargs:
            query += logic
        # pop and process the special keywords
        special = [k for k in kwargs.keys() if k in self.special_kw]
        for k in special:
            value = kwargs.pop(k)
            kwargs.update(self.special_kw[k].__func__(value))
        query += logic.join(('{k}:"{v}"{s}'.format(k=k, v=v, s=suffix)
                             for k, v in kwargs.items()
                             if v))
        return query

    def query(self, *args, **kwargs):
        self.params = {}
        if ('geometry') in kwargs:
            self.params['geometry'] = kwargs.pop('geometry')
        query = self._build_params(args, kwargs)
        self.params['query'] = query
        self.params['srsname'] = self.srs
        if self.rs:
            self.params['rs'] = self.rs
        self.r = requests.get(self.url, params=self.params)
        # ToDo raise specific errors
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        return self.r.json()['features']


