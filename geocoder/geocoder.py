#!/usr/bin/env python
#coding:utf-8

from qgis.PyQt.QtCore import pyqtSignal, QObject, QThread
from qgis.core import QgsFeature, QgsFeatureIterator
from typing import Union
import re
import math


class FieldMap:
    '''
    map fields of layer to parameters for geocoders
    '''
    def __init__(self, layer, ignore=[], keywords={}):
        # key: field name, value: (active, keyword)
        # active means, if the field should be used for geocoding
        # keyword maps the field to an argument of the geocoder
        self._mapping = {}
        self.layer = layer
        items = keywords.items()
        keys = [i[0] for i in items]
        kv_flat = [item.lower() for sublist in items for item in sublist]
        for field in layer.fields():
            name = field.name()
            if name in ignore:
                continue
            idx = kv_flat.index(name.lower()) // 2 if name.lower() in kv_flat \
                else -1
            keyword = keys[idx] if idx >= 0 else None
            active = True if idx >= 0 else False
            self._mapping[name] = [active, keyword]

    def valid(self, layer):
        for field in layer.fields():
            if field.name() not in self._mapping:
                return False
        return True

    def fields(self):
        return self._mapping.keys()

    def set_field(self, field_name: str, keyword: str=None, active: bool=None):
        if keyword is not None:
            self.set_keyword(field_name, keyword)
        if active is not None:
            self.set_active(field_name, active=active)

    def set_active(self, field_name, active=True):
        self._mapping[field_name][0] = active

    def set_keyword(self, field_name, keyword):
        self._mapping[field_name][1] = keyword

    def active(self, field_name):
        return self._mapping[field_name][0]

    def keyword(self, field_name):
        return self._mapping[field_name][1]

    def to_args(self, feature):
        kwargs = {}
        args = []
        attributes = feature.attributes()
        for field_name, (active, key) in self._mapping.items():
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
        for field_name, (active, key) in self._mapping.items():
            if active:
                i += 1
        return i


class Geocoder:

    # keywords used in  and their display name for the ui
    keywords = {}

    def __init__(self, url='', srs='EPSG:4326'):
        self.url = url
        self.srs = srs

    def query(self, *args, **kwargs):
        raise NotImplementedError


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


class Worker(QThread):
    '''
    abstract worker
    '''

    # available signals to be used in the concrete worker
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    message = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, parent=None):
        QObject.__init__(self, parent=parent)
        self.is_killed = False

    def run(self):
        '''
        runs code defined in self.work
        emits self.finished on success and self.error on exception
        override this function if you make asynchronous calls
        '''
        try:
            result = self.work()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def work(self):
        raise NotImplementedError

    def kill(self):
        self.is_killed = True


class Geocoding(Worker):
    feature_done = pyqtSignal(QgsFeature, list)

    def __init__(self, geocoder: Geocoder, layer_map: FieldMap,
                 features: Union[QgsFeatureIterator, list]=None, parent=None):
        super().__init__(parent=parent)
        self.geocoder = geocoder
        self.layer_map = layer_map
        features = features or layer_map.layer.getFeatures()
        self.features = [f for f in features]

    def work(self):
        if not self.geocoder:
            self.error('no geocoder set')
            return False
        success = True
        features = [f for f in self.features]
        count = len(features)
        for i, feature in enumerate(features):
            if self.is_killed:
                success = False
                self.error('Anfrage abgebrochen', color='red')
                break
            args, kwargs = self.layer_map.to_args(feature)
            try:
                res = self.geocoder.query(*args, **kwargs)
                self.feature_done.emit(feature, res)
                message = (f'Feature {feature.id()} -> '
                           f'<b>{len(res)} </b> Ergebnis(se)')
                self.message.emit(message)
            except Exception as e:
                success = False
                self.error.emit(str(e))
            finally:
                progress = math.floor(100 * (i + 1) / count)
                self.progress.emit(progress)

        return success


