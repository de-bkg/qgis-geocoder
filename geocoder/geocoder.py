#!/usr/bin/env python
#coding:utf-8

from qgis.PyQt.QtCore import pyqtSignal, QObject
import numpy as np
import re
import math


class Geocoder:

    # keywords used in  and their display name for the ui
    keywords = {}

    def __init__(self, url='', srs='EPSG:4326'):
        self.url = url
        self.srs = srs


class ResultCache:
    '''
    cache for storing result collections intermediately
    ToDo: filebased caching (might use too much memory in current state)
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
    result of single geocoding
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
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    message = pyqtSignal(str)
    progress = pyqtSignal(float)

    def __init__(self):
        QObject.__init__(self)
        self.is_killed = False

    def run(self):
        success = self.work()
        self.finished.emit(success)

    def work(self):
        raise NotImplementedError

    def kill(self):
        self.is_killed = True


class Geocoding(Worker):
    feature_done = pyqtSignal(int, Results)

    def __init__(self, layer, geocoder: Geocoder):
        super().__init__()
        self.geocoder = geocoder
        self.field_map = FieldMap(layer)
        self.layer = layer

    def set_field(self, field_name: str, keyword: str=None, active: bool=None):
        if keyword is not None:
            self.field_map.set_keyword(field_name, keyword)
        if active is not None:
            self.field_map.set_active(field_name, active=active)

    def work(self):
        success = True
        features = self.layer.getFeatures()
        count = self.layer.featureCount()
        for i, feature in enumerate(features):
            if self.is_killed:
                success = False
                break
            args, kwargs = self.field_map.to_args(feature)
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
                success = False
                self.error.emit(str(e))
            finally:
                progress = math.floor(100 * (i + 1) / count)
                self.progress.emit(progress)

        return success


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

    def valid(self, layer):
        for field in layer.fields():
            if field.name() not in self.mapping:
                return False
        return True

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

