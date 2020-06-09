# -*- coding: utf-8 -*-
'''
***************************************************************************
    database.py
    ---------------------
    Date                 : March 2020
    Copyright            : (C) 2020 by Christoph Franke
    Email                : franke at ggr-planung dot de
***************************************************************************
*                                                                         *
*   This program is free software: you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 3 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
'''

'''
generic database interface and features using this interface
'''

__author__ = 'Christoph Franke'
__date__ = '16/03/2020'
__copyright__ = 'Copyright 2020, Bundesamt für Kartographie und Geodäsie'

from qgis.PyQt.QtCore import pyqtSignal, QObject, QThread
from qgis.core import QgsFeature, QgsFeatureIterator, QgsVectorLayer
from typing import Union
import re
import math
import copy


class FieldMap:
    '''
    map fields of QGIS vector layer to parameters as input for geocoders.
    fields can be assigned to geocoding parameters and be set active,
    meaning that they will be used as inputs for geocoding

    Attributes
    ----------
    layer : QgsVectorLayer
        mapped vector layer
    '''
    def __init__(self, layer: QgsVectorLayer, ignore: list=[],
                 keywords: dict ={}):
        '''
        Parameters
        ----------
        layer : QgsVectorLayer
            the vector layer to be mapped
        ignore : list, optional
            field names to ignore (will not be mappable)
        keywords : dict, optional
            dictionary of available parameters for the geocoder,
            pretty names (as displayed in UI) as keys and parameter names as
            values (as used for geocoding).
            fields of layers matching either the keys or the values will be
            automatically be assigned and set active (all other fields are not
            active by default)
        '''
        # dict holding the mapping, key: field name, value: (active, keyword)
        self._mapping = {}
        self.layer = layer
        items = keywords.items()
        keys = [i[0] for i in items]
        kv_flat = [item.lower() for sublist in items for item in sublist]
        # put all fields of the layer into the map dict
        for field in layer.fields():
            name = field.name()
            if name in ignore:
                continue
            # automatically assign fields to matching keywords (either the
            # pretty name or the actual parameter name) and set them
            # active if matched, all other fields are not active by default
            idx = kv_flat.index(name.lower()) // 2 if name.lower() in kv_flat \
                else -1
            keyword = keys[idx] if idx >= 0 else None
            active = True if idx >= 0 else False
            self._mapping[name] = [active, keyword]

    def valid(self, layer: QgsVectorLayer) -> bool:
        '''
        check if this field map is applyabble to the given layer.
        layer has to contain all mapped field names to be valid

        Parameters
        ----------
        layer : QgsVectorLayer
            the vector layer to be checked

        Returns
        -------
        bool
            field map is valid for given layer
        '''
        field_names = [f.name() for f in layer.fields()]
        for mapped in self._mapping.keys():
            if mapped not in field_names:
                return False
        return True

    def copy(self, layer: QgsVectorLayer=None) -> 'FieldMap':
        '''
        clone field map with current mapping,

        Parameters
        ----------
        layer : QgsVectorLayer, optional
            sets layer of field map, defaults to current layer of field map

        Returns
        -------
        FieldMap
            clone of field map
        '''
        clone = FieldMap(layer or self.layer)
        clone._mapping = copy.deepcopy(self._mapping)
        return clone

    def fields(self) -> list:
        '''
        Returns
        -------
        list
            mapped fields of mapped layer
        '''
        return list(self._mapping.keys())

    def set_field(self, field_name: str, keyword: str=None, active: bool=None):
        '''
        set properties of a mapped field

        Parameters
        ----------
        field_name : str
            name of the field
        keyword : str, optional
            sets keyword as used for geocoding
        active : bool, optional
            sets active status to field. if True field will be used for
            geocoding
        '''
        if keyword is not None:
            self.set_keyword(field_name, keyword)
        if active is not None:
            self.set_active(field_name, active=active)

    def set_active(self, field_name: str, active: bool=True):
        '''
        sets active status to field

        Parameters
        ----------
        field_name : str
            name of the field
        active : bool
            active status to field. if True field will be used for
            geocoding
        '''
        self._mapping[field_name][0] = active

    def set_keyword(self, field_name: str, keyword: str):
        '''
        set keyword of field

        Parameters
        ----------
        field_name : str
            name of the field
        keyword : str
            keyword used in geocoding
        '''

    def active(self, field_name: str):
        '''
        active status of field

        Parameters
        ----------
        field_name : str
            name of the field

        Returns
        ----------
        bool
            True, if field will be used in geocoding
            False, if it is not in use
        '''
        return self._mapping[field_name][0]

    def keyword(self, field_name: str):
        '''
        keyword how field is used in geocoding

        Parameters
        ----------
        field_name : str
            name of the field

        Returns
        ----------
        str
             keyword used in geocoding
        '''
        return self._mapping[field_name][1]

    def to_args(self, feature: QgsFeature) -> tuple:
        '''
        creates parameters out of the mapped (active) fields and current values
        to be used in geocoding, inactive fields and fields with no values are
        skipped

        Parameters
        ----------
        feature : QgsFeature
            feature to geocode

        Returns
        ----------
        (list, dict)
            values of mapped fields without keywords are returned in the list,
            the dictionary contains the keywords as keys and the current values
            of the mapped fields as values
        '''
        kwargs = {}
        args = []
        attributes = feature.attributes()
        for field_name, (active, keyword) in self._mapping.items():
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
            if keyword is None:
                split = re.findall(r"[\w'\-]+", value)
                args.extend(split)
            else:
                kwargs[keyword] = value
        return args, kwargs

    def count_active(self) -> int:
        '''
        get number of mapped fields where active status is set True

        Returns
        ----------
        int
            number of active mapped fields
        '''
        i = 0
        for field_name, (active, key) in self._mapping.items():
            if active:
                i += 1
        return i


class Geocoder:
    '''
    abstract geocoder
    '''

    # keywords used in  and their display name for the ui
    keywords = {}

    def __init__(self, url: str='', crs: str='EPSG:4326'):
        '''
        Parameters
        ----------
        url : str, optional
            url of geocoding service
        crs : str, optional
            code of projection, defaults to epsg 4326
        '''
        self.url = url
        self.crs = crs

    def query(self, *args, **kwargs):
        '''
        to be implemented by derived classes

        Parameters
        ----------
        *args
            query parameters without keyword
        **kwargs
            query parameters with keyword and value

        Returns
        ----------
        list
            list of geojson features
        '''
        raise NotImplementedError


class Worker(QThread):
    '''
    abstract worker

    Attributes
    ----------
    finished : pyqtSignal
        emitted when all tasks are finished, success True/False
    error : pyqtSignal
        emitted on error while working, error messafe
    message : pyqtSignal
        emitted when a message is send, message
    progress : pyqtSignal
        emitted on progress, progress in percent
    '''

    # available signals to be used in the concrete worker
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    message = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, parent: QObject=None):
        '''
        Parameters
        ----------
        parent : QObject, optional
            parent object of thread, defaults to no parent (global)
        '''
        QObject.__init__(self, parent=parent)
        self.is_killed = False

    def run(self):
        '''
        runs code defined in self.work
        emits self.finished on success and self.error on exception
        override this function if you want to make asynchronous calls
        '''
        try:
            result = self.work()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def work(self):
        '''
        override this to implement the code to be processed
        '''
        raise NotImplementedError

    def kill(self):
        '''
        call to abort geocoding
        '''
        self.is_killed = True


class Geocoding(Worker):
    '''
    Geocode QGIS Features, usable with different Geocoder implementations

    Attributes
    ----------
    finished : pyqtSignal
        emitted when all features are geocoded, success True/False
    error : pyqtSignal
        emitted on error while working, error messafe
    message : pyqtSignal
        emitted when a message is send, message
    progress : pyqtSignal
        emitted on progress, progress in percent
    feature_done : pyqtSignal
        emitted when feature is done,
        (processed feature, list of geocoded geojson features)
    '''

    feature_done = pyqtSignal(QgsFeature, list)

    def __init__(self, geocoder: Geocoder, field_map: FieldMap,
                 features: Union[QgsFeatureIterator, list]=None,
                 parent: QObject=None):
        '''
        Parameters
        ----------
        geocoder : Geocoder
            the geocoder used to geocode the features
        field_map : FieldMap
            mapped fields of the layer whose features are to be geocoded
        features : QgsFeatureIterator or list of QgsFeatures, optional
            features to be geocoded, defaults to all features in layer of
            field_map
        parent : QObject, optional
            parent object of thread, defaults to no parent (global)
        '''
        super().__init__(parent=parent)
        self.geocoder = geocoder
        self.field_map = field_map
        features = features or field_map.layer.getFeatures()
        self.features = [f for f in features]

    def work(self):
        '''
        process the geocoding of features
        '''
        if not self.geocoder:
            self.error('no geocoder set')
            return False
        success = True
        count = len(self.features)
        for i, feature in enumerate(self.features):
            if self.is_killed:
                success = False
                self.error.emit('Anfrage abgebrochen')
                break
            try:
                self.process(feature)
            except Exception as e:
                success = False
                self.error.emit(f'Feature {feature.id()} -> {e}')
            finally:
                progress = math.floor(100 * (i + 1) / count)
                self.progress.emit(progress)

        return success

    def process(self, feature: QgsFeature):
        '''
        geocode a single feature

        Parameters
        ----------
        feature : QgsFeature
            the feature with address fields matching the field_map to find
            point geometries for
        '''
        args, kwargs = self.field_map.to_args(feature)
        res = self.geocoder.query(*args, **kwargs)
        self.feature_done.emit(feature, res)
        message = (f'Feature {feature.id()} -> '
                   f'<b>{len(res)} </b> Ergebnis(se)')
        self.message.emit(message)


class ReverseGeocoding(Geocoding):
    '''
    Reverse geocode QGIS Features, usable with different Geocoder
    implementations

    Attributes
    ----------
    finished : pyqtSignal
        emitted when all features are reverse geocoded, success True/False
    error : pyqtSignal
        emitted on error while working, error messafe
    message : pyqtSignal
        emitted when a message is send, message
    progress : pyqtSignal
        emitted on progress, progress in percent
    feature_done : pyqtSignal
        emitted when feature is done,
        (processed feature, list of geojson features with addresses)
    '''

    def __init__(self, geocoder: Geocoder,
                 features: Union[QgsFeatureIterator, list],
                 parent: QObject=None):
        '''
        Parameters
        ----------
        geocoder : Geocoder
            the geocoder used to reverse geocode the features
        features : QgsFeatureIterator or list of QgsFeatures
            features to be reverse geocoded
        parent : QObject, optional
            parent object of thread, defaults to no parent (global)
        '''
        Worker.__init__(self, parent=parent)
        self.geocoder = geocoder
        self.features = [f for f in features]

    def process(self, feature: QgsFeature):
        '''
        reverse geocode single features

        Parameters
        ----------
        feature : QgsFeature
            the feature with point geometry to find addresses for
        '''
        pnt = feature.geometry().asPoint()
        res = self.geocoder.reverse(pnt.x(), pnt.y())
        self.feature_done.emit(feature, res)
        message = (f'Feature {feature.id()} -> '
                   f'<b>{len(res)} </b> Ergebnis(se)')
        self.message.emit(message)