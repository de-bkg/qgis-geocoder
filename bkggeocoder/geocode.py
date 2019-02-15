#!/usr/bin/env python
#coding:utf-8

from PyQt5.QtCore import QThread, pyqtSignal, QObject
import requests
import numpy as np
import re
import math


class ResultCache:
    '''
    cache for storing result collections intermediately
    ToDo: filebased caching (might use too much mem in current state)
    '''
    def __init__(self):
        self.results = {}

    def add(self, layer, feat_id, results):
        res_feat_store = self.results.get(layer.id())
        if not res_feat_store:
            res_feat_store = self.results[layer.id()] = {}
        self.results[layer.id()][feat_id] = results

    def get(self, layer, feat_id):
        res_layer = self.results.get(layer.id())
        if res_layer:
            return res_layer.get(feat_id)
        return None


class Results:
    '''
    collection of geocoding results
    '''
    def __init__(self):
        self.results = []

    def add(self, result):
        self.results.append(result)

    def best(self):
        if len(self.results) == 0:
            return None, -1
        scores = np.array([res.score for res in self.results])
        best_idx = scores.argmax()
        return self.results[best_idx], best_idx

    def count(self):
        return len(self)

    def __len__(self):
        return len(self.results)

    def __repr__(self):
        return '\n'.join(str(r) for r in self.results)

    def __iter__(self):
        return self.results.__iter__()

    def __getitem__(self, i):
        return self.results[i]


class Result:
    '''
    geocoding result
    '''
    def __init__(self, coordinates=[0, 0], text='', score=0, typ=None):
        self.coordinates = coordinates
        self.text = text
        self.score = score
        self.typ = typ

    def __repr__(self):
        return 'Typ: {typ} | Score: {score} | {text} @ {coords} '.format(
            typ=self.typ, coords=self.coordinates,
            text=self.text, score=self.score
        )


class Worker(QObject):
    '''
    abstract worker
    '''

    # available signals to be used in the concrete worker
    finished = pyqtSignal()
    error = pyqtSignal(str)
    message = pyqtSignal(str)
    progress = pyqtSignal(float)

    def __init__(self):
        QObject.__init__(self)
        self.is_killed = False

    def run(self):
        result = self.work()
        self.finished.emit()

    def work(self):
        raise NotImplementedError

    def kill(self):
        self.is_killed = True


class GeocodeWorker(Worker):
    '''
    worker for threaded geocoding
    '''
    feature_done = pyqtSignal(int, Results)

    def __init__(self, geocoder, queries):
        super().__init__()
        self.geocoder = geocoder
        self.queries = queries

    def work(self):
        count = len(self.queries)
        for i, (id, (args, kwargs)) in enumerate(self.queries):
            if self.is_killed:
                break
            try:
                results = self.geocoder.query(*args, **kwargs)
                #self.message.emit(self.geocoder.r.url)
                self.feature_done.emit(id, results)
                message = 'Feature {id} -> <b>{c}</b> Ergebnis(se)'.format(
                    id=id, c=results.count())
                if results.count() > 0:
                    best, idx = results.best()
                    message += '- bestes E.: {res}'.format(res=str(best))
                self.message.emit(message)
            except Exception as e:
                self.error.emit(str(e))
            finally:
                progress = math.floor(100 * (i + 1) / count)
                self.progress.emit(progress)


class FieldMap:
    '''
    map fields of layer to parameters for geocoders
    '''
    def __init__(self, layer):
        # key: field name, value: (active, keyword)
        # active means, if the field should be used for geocoding
        # keyword maps the field to an argument of the geocoder
        self.mapping = {}
        for field in layer.fields():
            self.mapping[field.name()] = [False, None]

    def set_active(self, field_name, active=True):
        self.mapping[field_name][0] = active

    def set_keyword(self, field_name, keyword):
        self.mapping[field_name][1] = keyword

    def active(self, field_name):
        return self.mapping[field_name][0]

    def keyword(self, field_name):
        return self.mapping[field_name][1]

    def to_args(self, feature):
        kwargs = {}
        args = []
        attributes = feature.attributes()
        for field_name, (active, key) in self.mapping.items():
            if not active:
                continue
            attributes = feature.attributes()
            idx = feature.fieldNameIndex(field_name)
            value = attributes[idx]
            if not value:
                continue
            if isinstance(value, float):
                value = int(value)
            value = str(value)
            if key is None:
                split = re.findall(r"[\w'\-]+", value)
                args.extend(split)
            else:
                kwargs[key] = value
        return args, kwargs

    def count_active(self):
        i = 0
        for field_name, (active, key) in self.mapping.items():
            if active:
                i += 1
        return i


class Geocoder:

    def __init__(self, url='', srs='EPSG:4326'):
        self.url = url
        self.srs = srs


class BKGGeocoder(Geocoder):
    '''
    geocoder using the BKG API
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

    logic_link = 'AND'
    fuzzy = False

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
        params = {}
        if ('geometry') in kwargs:
            params['geometry'] = kwargs.pop('geometry')
        query = self._build_params(args, kwargs)
        params['query'] = query
        params['srsname'] = self.srs
        self.r = requests.get(self.url, params=params)
        # ToDo raise specific errors
        if self.r.status_code != 200:
            raise Exception(self.r.text)
        results = self._postprocess(self.r.json())
        return results

    def _postprocess(self, json):
        results = Results()
        for feature in json['features']:
            geom = feature['geometry']
            properties = feature['properties']
            results.add(Result(
                coordinates=geom['coordinates'],
                text=properties['text'],
                score=properties['score'],
                typ=properties['typ']
            ))
        return results


