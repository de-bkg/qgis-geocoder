# -*- coding: utf-8 -*-
'''
***************************************************************************
    utils.py
    ---------------------
    Date                 : April 2020
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

utility functions used by the UI
'''

__author__ = 'Christoph Franke'
__date__ = '02/04/2020'

from typing import List
from qgis.core import (QgsVectorLayer, QgsProject, QgsCoordinateTransform,
                       QgsRasterLayer, QgsCoordinateReferenceSystem, QgsFeature,
                       QgsNetworkAccessManager, QgsLayerTreeGroup, QgsGeometry,
                       QgsLayerTreeLayer, QgsField)
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QLayout
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import (QUrl, QEventLoop, QTimer, QUrlQuery,
                              QObject, pyqtSignal, QVariant)
import json


class ResField:
    '''
    represents an extra field to add to a layer to store results in (or
    anything else)
    '''
    def __init__(self, name: str, field_type: str,
                 field_variant: QVariant = None,
                 prefix: str = '', alias: str = None,  optional: bool = False):
        '''
        Parameters
        ----------
        name : str
            name of the field
        field_type : str
            field type (e.g. char, varchar, text, int, serial, double)
        field_variant : QVariant, optional
            variant type, is derived from field_type if not given
        prefix : str, optional
            prefix added to the field name, defaults to no prefix
        alias : str, optional
            pretty name of the field, defaults to given name
        optional : bool, optional
            marks field as optional or required, defaults to required
        '''
        self.name = name
        self.prefix = prefix
        self.alias = alias or self.name
        self.field_variant = field_variant or self._get_variant(field_type)
        self.field_type = field_type
        self.optional = optional

    @property
    def field_name(self):
        return self.name if not self.prefix \
            else f'{self.prefix}_{self.name}'

    def to_qgs_field(self) -> QgsField:
        '''
        representation of field as a QgsField, addable to a vector layer

        Returns
        -------
        QgsField
        '''
        return QgsField(self.field_name, self.field_variant,
                        typeName=self.field_type)

    def set_value(self, layer: QgsVectorLayer, feature_id: int, value: object,
                  auto_add: bool = True):
        '''
        set a value to the represented field of the feature with given id

        Parameters
        ----------
        layer : QgsVectorLayer
            the layer the feature is in
        feature_id : int
            id of the feature
        value : object
            the value to set
        auto_add : bool, optional
            add the field to the layer if it doesn't exist yet, defaults to True
        '''
        fidx = self.idx(layer)
        if fidx < 0:
            if auto_add:
                layer.dataProvider().addAttribute(self.to_qgs_field())
                layer.updateFields()
            else:
                return
        layer.changeAttributeValue(feature_id, fidx, value)

    def idx(self, layer: QgsVectorLayer) -> int:
        '''
        index of the field in given layer

        Parameters
        ----------
        layer : QgsVectorLayer
             the layer to look in

        Returns
        -------
        int
            index of the field, -1 if not found
        '''
        field_name = self.field_name_comp(layer)
        return layer.fields().indexFromName(field_name)

    def field_name_comp(self, layer: QgsVectorLayer) -> str:
        '''return compatible field name depending on data provider '''
        provider_type = layer.dataProvider().storageType()
        if provider_type == 'ESRI Shapefile':
            self.field_name[:10]
        return self.field_name

    @staticmethod
    def _get_variant(field_type):
        if field_type == 'bool':
            return QVariant.Bool
        if 'int' in field_type:
            return QVariant.Int
        if 'float' in field_type:
            return QVariant.Double
        return QVariant.String


class LayerWrapper():
    '''
    wrapper for vector layers to prevent errors when wrapped c++ layer is
    accessed after removal from the QGIS registry and to keep track of the id
    even after removal

    Attributes
    ----------
    id : int
        the id of the wrapped layer
    layer : QgsVectorLayer
        the wrapped vector layer, None if it was already removed from the
        registry
    '''
    def __init__(self, layer: QgsVectorLayer):
        '''
        Parameters
        ----------
        layer : QgsVectorLayer
            the vector layer to wrap
        '''
        self._layer = layer
        self.id = layer.id()

    @property
    def layer(self) -> QgsVectorLayer:
        # check if wrapped layer still excists
        try:
            if self._layer is not None:
                # have to call any function on layer to ensure
                self._layer.id()
        except RuntimeError:
            return None
        return self._layer


def clear_layout(layout: QLayout):
    '''
    empties layout by removing children and grand-children (complete hierarchy)
    of the layout recursively

    Parameters
    ----------
    layout : QLayout
        the layout to empty
    '''
    while layout.count():
        child = layout.takeAt(0)
        if not child:
            continue
        if child.widget():
            child.widget().deleteLater()
        elif child.layout() is not None:
            clear_layout(child.layout())

def clone_layer(layer: QgsVectorLayer, crs: str = 'EPSG:4326', name: str = None,
                features: List[QgsFeature] = None) -> QgsVectorLayer:
    '''
    Clone given layer in memory, adds Point geometry with given crs.
    Data of new layer is based on all features of origin layer OR given features

    Parameters
    ----------
    layer : QgsVectorLayer
        layer to clone
    name : str, optional
        name the cloned layer gets, defaults to no name
    features : list, optional
        list of features to put into the cloned layer, defaults to features of
        input layer
    crs : str, optional
        code of projection of the geometry of the cloned layer,
        defaults to epsg 4326

    Returns
    ----------
    QgsVectorLayer
        temporary layer with fields of input layer and point geometry, contains
        given features or features of the input layer
    '''
    features = features or layer.getFeatures()
    name = name or + f'{layer.name()}__clone'

    clone = QgsVectorLayer(f'Point?crs={crs}', name, 'memory')

    data = clone.dataProvider()
    attr = layer.dataProvider().fields().toList()
    data.setEncoding(layer.dataProvider().encoding())
    data.addAttributes(attr)
    clone.updateFields()
    data.addFeatures([f for f in features])
    return clone

def get_geometries(layer: QgsVectorLayer, selected: bool = False,
                   crs: str = None) -> List[QgsGeometry]:
    '''
    get the geometries of the features inside the layer,
    optionally transform them to given target crs

    Parameters
    ----------
    layer : QgsVectorLayer
        layer with features to get the geometries from
    selected : bool, optional
        return only the geometries of the selected layers,
        defaults to all features
    crs : str, optional
        code of projection of the returned geometries, defaults to
        original projection of input layer

    Returns
    ----------
    list
        list of geometries
    '''
    features = layer.selectedFeatures() if selected else layer.getFeatures()
    geometries = [f.geometry() for f in features]
    if crs:
        crs = QgsCoordinateReferenceSystem(crs)
        source_crs = layer.crs()
        trans = QgsCoordinateTransform(source_crs, crs,
                                       QgsProject.instance())
        for geom in geometries:
            geom.transform(trans)
    return geometries


class Layer:
    '''
    wrapper of a vector layer in the QGIS layer tree with some
    convenient functions. Can be grouped and addressed by its name.
    '''

    def __init__(self, layername: str, data_path: str, groupname: str = '',
                 prepend: bool = True):
        '''
        Parameters
        ----------
        layername : str
            name of the layer in the data source
        data_path : str
            path to the data source of the layer
        groupname : str, optional
            name of the parent group, will be created if not existing, can be
            nested by joining groups with '/' e.g. 'Projekt/Hintergrundkarten',
            defaults to add layer to the root of the layer tree
        prepend : bool
            prepend the group of the layer if True (prepends each group if
            nested), append if False, defaults to prepending the group
        '''
        self.layername = layername
        self.data_path = data_path
        self.layer = None
        self._l = None
        self.groupname = groupname
        self.prepend = prepend

    @property
    def parent(self) -> QgsLayerTreeGroup:
        '''
        the parent group of the layer
        '''
        parent = QgsProject.instance().layerTreeRoot()
        if self.groupname:
            parent = Layer.add_group(self.groupname, prepend=self.prepend)
        return parent

    @property
    def _tree_layer(self) -> QgsLayerTreeLayer:
        '''
        tree representation of the layer
        '''
        if not self.layer:
            return None
        return self.parent.findLayer(self.layer)

    @property
    def layer(self) -> QgsVectorLayer:
        '''
        the wrapped vector layer
        '''
        try:
            layer = self._layer
            if layer is not None:
                # call function on layer to check if it still exists
                layer.id()
        except RuntimeError:
            return None
        return layer

    @layer.setter
    def layer(self, layer: QgsVectorLayer):
        self._layer = layer

    @classmethod
    def add_group(cls, groupname: str, prepend: bool = True
                  ) -> QgsLayerTreeGroup:
        '''
        add a group to the layer tree

        Parameters
        ----------
        groupname : str
            name of the parent group, will be created if not existing, can be
            nested by joining groups with '/' e.g. 'Projekt/Hintergrundkarten'
        prepend : bool, optional
            prepend the group if True (prepends each group if nested),
            append if False, defaults to prepending the group

        Returns
        ----------
        QgsLayerTreeGroup
            the created group (the deepest one in hierarchy if nested)
        '''
        groupnames = groupname.split('/')
        parent = QgsProject.instance().layerTreeRoot()
        group = cls._nest_groups(parent, groupnames, prepend=prepend)
        return group

    @classmethod
    def _nest_groups(cls, parent: QgsLayerTreeGroup, groupnames: List[str],
                     prepend: bool = True) -> QgsLayerTreeGroup:
        '''recursively nests groups in order of groupnames'''
        if len(groupnames) == 0:
            return parent
        next_parent = parent.findGroup(groupnames[0])
        if not next_parent:
            next_parent = (parent.insertGroup(0, groupnames[0])
                           if prepend else parent.addGroup(groupnames[0]))
        return cls._nest_groups(next_parent, groupnames[1:], prepend=prepend)

    @classmethod
    def find(cls, label: str, groupname: str = '') -> List[QgsLayerTreeLayer]:
        '''
        deep find tree layer by name in a group recursively

        Parameters
        ----------
        label : str
            label of the tree layer
        groupname : str, optional
            name of the group to search in, can be nested by joining groups with
            '/' e.g. 'Projekt/Hintergrundkarten', defaults to searching in layer
            tree root

        Returns
        ----------
        list
            list of tree layers matching the name, empty list if none found
        '''
        parent = QgsProject.instance().layerTreeRoot()
        if groupname:
            groupnames = groupname.split('/')
            while groupnames:
                g = groupnames.pop(0)
                parent = parent.findGroup(g)
                if not parent:
                    return []

        def deep_find(node, label):
            found = []
            if node:
                for child in node.children():
                    if child.name() == label:
                        found.append(child)
                    found.extend(deep_find(child, label))
            return found

        found = deep_find(parent, label)
        return found

    def draw(self, style_path: str = None, label: str = '', redraw: str = True,
             checked: bool = True, filter: str = None, expanded: bool = True,
             prepend: bool = False) -> QgsVectorLayer:
        '''
        load the data into a vector layer, draw it and add it to the layer tree

        Parameters
        ----------
        label : str, optional
            label of the layer, defaults to layer name this is initialized with
        style_path : str, optional
            a QGIS style (.qml) can be applied to the layer, defaults to no
            style
        redraw : bool, optional
            replace old layer with same name in same group if True,
            only create if not existing if set to False, else it is refreshed,
            defaults to redrawing the layer
        checked: bool, optional
            set check state of layer in layer tree, defaults to being checked
        filter: str, optional
            QGIS filter expression to filter the layer, defaults to no filtering
        expanded: str, optional
            sets the legend to expanded or not, defaults to an expanded legend
        prepend: bool, optional
            prepend the layer to the other layers in its group if True,
            append it if False, defaults to appending the layer

        Returns
        ----------
        QgsVectorLayer
            the created, replaced or refreshed vector layer

        '''
        if not self.layer:
            layers = Layer.find(label, groupname=self.groupname)
            if layers:
                self.layer = layers[0].layer()
        if redraw:
            self.remove()
        else:
            iface.mapCanvas().refreshAllLayers()

        if not self.layer:
            self.layer = QgsVectorLayer(self.data_path, self.layername, "ogr")
            if label:
                self.layer.setName(label)
            QgsProject.instance().addMapLayer(self.layer, False)
            self.layer.loadNamedStyle(style_path)
        tree_layer = self._tree_layer
        if not tree_layer:
            tree_layer = self.parent.insertLayer(0, self.layer) if prepend else\
                self.parent.addLayer(self.layer)
        tree_layer.setItemVisibilityChecked(checked)
        tree_layer.setExpanded(expanded)
        if filter is not None:
            self.layer.setSubsetString(filter)
        return self.layer

    def set_visibility(self, state: bool):
        '''
        change check state of layer, layer is not visible if unchecked

        Parameters
        ----------
        state: bool
            set check state of layer in layer tree
        '''

        tree_layer = self._tree_layer
        if tree_layer:
            tree_layer.setItemVisibilityChecked(state)

    def zoom_to(self):
        '''
        zooms map canvas to the extent of this layer
        '''
        if not self.layer:
            return
        canvas = iface.mapCanvas()
        self.layer.updateExtents()
        transform = QgsCoordinateTransform(
            self.layer.crs(), canvas.mapSettings().destinationCrs(),
            QgsProject.instance())
        canvas.setExtent(transform.transform(self.layer.extent()))

    def remove(self):
        '''
        remove the layer from map and layer tree
        '''
        if not self.layer:
            return
        QgsProject.instance().removeMapLayer(self.layer.id())
        self.layer = None


class TileLayer(Layer):
    '''
    wrapper for a tile layer
    '''
    def __init__(self, url: str, groupname: str = '', prepend: bool = True):
        '''
        Parameters
        ----------
        url : str
            url of the tile layer service
        groupname : str, optional
            name of the parent group, will be created if not existing, can be
            nested by joining groups with '/' e.g. 'Projekt/Hintergrundkarten',
            defaults to adding layer to the root of the layer tree
        prepend : bool
            prepend the group of the layer if True (prepends each group if
            nested), append if False, defaults to prepending the group
        '''
        super().__init__(None, None, groupname=groupname, prepend=prepend)
        self.url = url
        self.prepend = prepend

    def draw(self, label: str, checked: bool = True, expanded: bool = True):
        '''
        create the tile layer, draw it and add it to the layer tree

        Parameters
        ----------
        label : str
            label of the layer as it appears in the layer tree
        expanded : bool, optional
            replace old layer with same name in same group if True,
            only create if not existing if set to False, else it is refreshed,
            defaults to redrawing the layer
        checked: bool, optional
            set check state of layer in layer tree, defaults to being checked
        '''
        self.layer = None
        for child in self.parent.children():
            if child.name() == label:
                self.layer = child.layer()
                break
        if not self.layer:
            self.layer = QgsRasterLayer(self.url, label, 'wms')
            QgsProject.instance().addMapLayer(self.layer, False)
            l = self.parent.insertLayer(0, self.layer) if self.prepend \
                else self.parent.addLayer(self.layer)
            l.setItemVisibilityChecked(checked)
            l.setExpanded(expanded)


class TopPlusOpen(TileLayer):
    '''
    BKG background layer © Bundesamt für Kartographie und Geodäsie 2020
    data source:
    https://sg.geodatenzentrum.de/web_public/Datenquellen_TopPlus_Open.pdf
    '''

    def __init__(self, groupname: str = '', prepend: bool = False,
                 crs: str = 'EPSG:4326', greyscale: bool = False):
        '''
        Parameters
        ----------
        groupname : str, optional
            name of the parent group, will be created if not existing, can be
            nested by joining groups with '/' e.g. 'Projekt/Hintergrundkarten',
            defaults to adding layer to the root of the layer tree
        prepend : bool
            prepend the group of the layer if True (prepends each group if
            nested), append if False, defaults to prepending the group
        crs : str, optional
            code of projection, defaults to epsg 4326
        greyscale: bool, optional
            display a greyscaled map if True, defaults to colored map
        '''
        layer = 'web_grau' if greyscale else 'web'
        url = (f'contextualWMSLegend=0&crs={crs}&dpiMode=7&featureCount=10'
               f'&format=image/png&layers={layer}&styles=default'
               '&tileMatrixSet=EU_EPSG_25832_TOPPLUS'
               '&url=https://sgx.geodatenzentrum.de/wmts_topplus_open/'
               '1.0.0/WMTSCapabilities.xml')
        super().__init__(url, groupname=groupname, prepend=prepend)


class Reply:
    '''
    wrapper of qnetworkreply to match interface of requests library
    '''
    def __init__(self, reply: QNetworkReply):
        '''
        Parameters
        ----------
        reply : QNetworkReply
            the reply of a QNetworkRequest to wrap
        '''
        self.reply = reply
        # streamed
        if hasattr(reply, 'readAll'):
            self.raw_data = reply.readAll()
        # reply received with blocking call
        else:
            self.raw_data = reply.content()

    @property
    def url(self) -> str:
        '''
        Returns
        ----------
        str
            the requested URL
        '''
        return self.reply.url().url()

    @property
    def status_code(self) -> int:
        '''
        Returns
        ----------
        int
            the HTML status code returned by the requested server
        '''
        return self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

    @property
    def content(self) -> str:
        '''
        Returns
        ----------
        str
            the response of the server
        '''
        return self.raw_data.data()

    def raise_for_status(self):
        '''
        raise error when request was not successful
        '''
        if self.status_code != 200:
            raise ConnectionError(self.status_code)

    def json(self) -> dict:
        '''
        parse response into a json object

        Returns
        ----------
        dict
            the response as a json-style dictionary
        '''
        return json.loads(self.content)

    @property
    def headers(self) -> dict:
        '''
        Returns
        ----------
        dict
            the headers of the response
        '''
        headers = {}
        for h in ['ContentDispositionHeader', 'ContentTypeHeader',
                  'LastModifiedHeader', 'ContentLengthHeader',
                  'CookieHeader', 'LocationHeader',
                  'UserAgentHeader', 'LocationHeader']:
            headers[h] = self.reply.header(getattr(QNetworkRequest, h))
        return headers


class Request(QObject):
    '''
    Wrapper of QgsNetworkAccessManager to match interface of requests library,
    can make synchronous or asynchronous calls

    ensures compatibility of synchronous requests with QGIS versions prior 3.6

    Attributes
    ----------
    finished : pyqtSignal
        emitted when the request is done and the server responded, Reply
    error : pyqtSignal
        emitted on error, error message
    progress : pyqtSignal
        emitted on progress, percentage of progress
    '''
    finished = pyqtSignal(Reply)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, synchronous: bool = True):
        '''
        Parameters
        ----------
        synchronous : bool, optional
            requests are made either synchronous (True) or asynchronous (False),
            defaults to synchronous calls
        '''
        super().__init__()
        self.synchronous = synchronous

    @property
    def _manager(self) -> QgsNetworkAccessManager:
        return QgsNetworkAccessManager.instance()

    def get(self, url: str, params: dict = None,
            timeout: int = 10000, **kwargs) -> Reply:
        '''
        queries given url (GET)

        Parameters
        ----------
        url : str
            the url to request
        params : dict, optional
            query parameters with the parameters as keys and the values as
            values, defaults to no query parameters
        timeout : int, optional
            the timeout of synchronous requests in milliseconds, will be ignored
            when making asynchronous requests, defaults to 10000 ms
        **kwargs :
            additional parameters matching the requests interface will
            be ignored (e.g. verify is not supported)

        Returns
        ----------
        Reply
           the response is returned in case of synchronous calls, if you are
           using asynchronous calls retrieve the response via the finished-
           signal instead
        '''
        qurl = QUrl(url)

        if params:
            query = QUrlQuery()
            for param, value in params.items():
                query.addQueryItem(param, str(value))
            qurl.setQuery(query.query())

        if self.synchronous:
            return self._get_sync(qurl, timeout=timeout)

        return self._get_async(qurl)

    def post(self, url, params: dict = None, data: bytes = b'',
             timeout: int = 10000, **kwargs) -> Reply:
        '''
        posts data to given url (POST)

        asynchronous posts are not implemented yet

        Parameters
        ----------
        url : str
            the url to post to
        params : dict, optional
            query parameters with the parameters as keys and the values as
            values, defaults to no query parameters
        data : bytes, optional
            the data to post as a byte-string, defaults to no data posted
        timeout : int, optional
            the timeout of synchronous requests in milliseconds, will be ignored
            when making asynchronous requests, defaults to 10000 ms
        **kwargs :
            additional parameters matching the requests-interface will
            be ignored (e.g. verify is not supported)

        Returns
        ----------
        Reply
           the response is returned in case of synchronous calls, if you are
           using asynchronous calls retrieve the response via the finished-
           signal instead
        '''
        qurl = QUrl(url)

        if params:
            query = QUrlQuery()
            for param, value in params.items():
                query.addQueryItem(param, str(value))
            qurl.setQuery(query.query())

        if self.synchronous:
            return self._post_sync(qurl, timeout=timeout, data=data)

        return self._post_async(qurl)


    def _get_sync(self, qurl: QUrl, timeout: int = 10000) -> Reply:
        '''
        synchronous GET-request
        '''
        request = QNetworkRequest(qurl)
        ## newer versions of QGIS (3.6+) support synchronous requests
        #if hasattr(self._manager, 'blockingGet'):
            #reply = self._manager.blockingGet(request, forceRefresh=True)
        ## use blocking event loop for older versions
        #else:
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        # reply or timeout break event loop, whoever comes first
        timer.timeout.connect(loop.quit)
        reply = self._manager.get(request)
        reply.finished.connect(loop.quit)

        timer.start(timeout)

        # start blocking loop
        loop.exec()
        loop.deleteLater()
        if not timer.isActive():
            reply.deleteLater()
            raise ConnectionError('Timeout')

        timer.stop()
        #if reply.error():
            #self.error.emit(reply.errorString())
            #raise ConnectionError(reply.errorString())
        res = Reply(reply)
        self.finished.emit(res)
        return res

    def _get_async(self, qurl: QUrl):
        '''
        asynchronous GET-request
        '''
        request = QNetworkRequest(qurl)

        def progress(b, total):
            if total > 0:
                self.progress.emit(int(100*b/total))

        self.reply = self._manager.get(request)
        self.reply.error.connect(
            lambda: self.error.emit(self.reply.errorString()))
        self.reply.downloadProgress.connect(progress)
        self.reply.finished.connect(
            lambda: self.finished.emit(Reply(self.reply)))
        #self.reply.readyRead.connect(ready_read)
        #return 0

    def _post_sync(self, qurl: QUrl, timeout: int = 10000, data: bytes = b''):
        '''
        synchronous POST-request
        '''
        request = QNetworkRequest(qurl)
        # newer versions of QGIS (3.6+) support synchronous requests
        if hasattr(self._manager, 'blockingPost'):
            reply = self._manager.blockingPost(request, data, forceRefresh=True)
        # use blocking event loop for older versions
        else:
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            # reply or timeout break event loop, whoever comes first
            timer.timeout.connect(loop.quit)
            reply = self._manager.post(request, data)
            reply.finished.connect(loop.quit)

            timer.start(timeout)

            # start blocking loop
            loop.exec()
            loop.deleteLater()
            if not timer.isActive():
                reply.deleteLater()
                raise ConnectionError('Timeout')

            timer.stop()
        if reply.error():
            self.error.emit(reply.errorString())
            raise ConnectionError(reply.errorString())
        res = Reply(reply)
        self.finished.emit(res)
        return res

    def _post_async(self, qurl: QUrl):
        '''
        asynchronous POST-request

        not implemented yet
        '''
        raise NotImplementedError

