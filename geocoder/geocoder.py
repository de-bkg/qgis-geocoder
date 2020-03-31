#!/usr/bin/env python
#coding:utf-8

from qgis.PyQt.QtCore import pyqtSignal, QObject
from qgis.core import QgsFeature
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
    feature_done = pyqtSignal(QgsFeature, list)

    def __init__(self, layer, geocoder: Geocoder, ignore: list=[]):
        super().__init__()
        self.geocoder = geocoder
        # ToDo: what if fields are removed by user later? events
        self.field_mapping = {}
        for field in layer.fields():
            name = field.name()
            if name in ignore:
                continue
            self.field_mapping[name] = [False, None]
        self.layer = layer

    def fields(self):
        return self.mapping.keys()

    def active(self, field_name: str):
        return self.active(field_name)

    def set_field(self, field_name: str, keyword: str=None, active: bool=None):
        if keyword is not None:
            self.set_keyword(field_name, keyword)
        if active is not None:
            self.set_active(field_name, active=active)

    def work(self):
        success = True
        features = self.layer.getFeatures()
        count = self.layer.featureCount()
        for i, feature in enumerate(features):
            if self.is_killed:
                success = False
                break
            args, kwargs = self.to_args(feature)
            try:
                results = self.geocoder.query(*args, **kwargs)
                #self.message.emit(self.geocoder.r.url)
                self.feature_done.emit(feature, results)
                message = (f'Feature {feature} -> '
                           f'<b>{len(results)} </b> Ergebnis(se)')
                #if results.count() > 0:
                    #best, idx = results.best()
                    #message += '- bestes E.: {res}'.format(res=str(best))
                self.message.emit(message)
            except Exception as e:
                success = False
                self.error.emit(str(e))
            finally:
                progress = math.floor(100 * (i + 1) / count)
                self.progress.emit(progress)

        return success

    #def valid(self, layer):
        #for field in layer.fields():
            #if field.name() not in self.field_mapping:
                #return False
        #return True

    def set_active(self, field_name, active=True):
        self.field_mapping[field_name][0] = active

    def set_keyword(self, field_name, keyword):
        self.field_mapping[field_name][1] = keyword

    def active(self, field_name):
        return self.field_mapping[field_name][0]

    def keyword(self, field_name):
        return self.field_mapping[field_name][1]

    def to_args(self, feature):
        kwargs = {}
        args = []
        attributes = feature.attributes()
        for field_name, (active, key) in self.field_mapping.items():
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
        for field_name, (active, key) in self.field_mapping.items():
            if active:
                i += 1
        return i


