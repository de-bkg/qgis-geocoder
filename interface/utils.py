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
                       QgsRasterLayer, QgsCoordinateReferenceSystem, QgsFeature)
from qgis.utils import iface
from qgis.core import (QgsVectorLayer, QgsGeometry, QgsLayerTreeGroup,
                       QgsLayerTreeLayer)
from qgis.PyQt.QtWidgets import QLayout

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
    QgsProject.instance().addMapLayer(clone)
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
    def find(self, label: str, groupname: str = '') -> List[QgsLayerTreeLayer]:
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
