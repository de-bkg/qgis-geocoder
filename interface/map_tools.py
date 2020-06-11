# -*- coding: utf-8 -*-
'''
***************************************************************************
    map_tools.py
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

collection of tools for interacting with the map canvas
'''

__author__ = 'Christoph Franke'
__date__ = '08/04/2020'

from qgis import utils
from typing import List
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QCursor, QColor
from qgis.PyQt.Qt import QWidget
from qgis.gui import (QgsMapToolEmitPoint, QgsMapToolIdentify, QgsVertexMarker,
                      QgsMapCanvas)
from qgis.core import (QgsPointXY, QgsVectorLayer)


class MapTool:
    '''
    abstract class for tools triggered by clicking a certain ui element

    Attributes
    ----------
    cursor : QCursor
        the appearance of the cursor when hovering the map canvas while tool is
        active
    '''
    cursor = QCursor(Qt.CrossCursor)

    def __init__(self, ui_element: QWidget, canvas: QgsMapCanvas = None):
        '''
        Parameters
        ----------
        ui_element : QWidget
            clickable UI element, clicking on it will adctivate/deactivate this
            tool
        canvas : QgsMapCanvas, optional
            the map canvas the tool will work on, defaults to the map canvas of
            the QGIS UI
        '''
        self.ui_element = ui_element
        self.canvas = canvas or utils.iface.mapCanvas()
        self.ui_element.clicked.connect(
            lambda checked: self.set_active(checked))

    def set_active(self, active: bool):
        '''
        activate/deactivate the tool

        Parameters
        ----------
        active : bool
            activate tool if True, deactivate the tool if False
        '''
        if active:
            self.canvas.setMapTool(self)
            self.canvas.mapToolSet.connect(self.disconnect)
            self.canvas.setCursor(self.cursor)
        else:
            self.canvas.unsetMapTool(self)
            self.ui_element.blockSignals(True)
            self.ui_element.setChecked(False)
            self.ui_element.blockSignals(False)

    def disconnect(self, **kwargs: object):
        '''
        disconnect the tool from the map canvas
        '''
        self.canvas.mapToolSet.disconnect(self.disconnect)
        self.set_active(False)


class FeaturePicker(MapTool, QgsMapToolEmitPoint):
    '''
    tool for picking features on the map canvas by clicking

    Attributes
    ----------
    feature_picked : pyqtSignal
        emitted when a feature is clicked on the map canvas, feature id
    '''
    feature_picked = pyqtSignal(int)

    def __init__(self, ui_element: QWidget, layers: List[QgsVectorLayer] = [],
                 canvas: QgsMapCanvas = None):
        '''
        Parameters
        ----------
        ui_element : QWidget
            clickable UI element, clicking on it will adctivate/deactivate this
            tool
        layers : list, optional
            the layers containing the features that can be picked,
            defaults to not setting any layers
        canvas : QgsMapCanvas, optional
            the map canvas the tool will work on, defaults to the map canvas of
            the QGIS UI
        '''
        MapTool.__init__(self, ui_element, canvas=canvas)
        QgsMapToolEmitPoint.__init__(self, canvas=self.canvas)
        self._layers = layers

    def add_layer(self, layer: QgsVectorLayer):
        '''
        add a layer to pick features from

        Parameters
        ----------
        layer : QgsVectorLayer
            the layer containing the features that can be picked
        '''
        if layer:
            self._layers.append(layer)

    def set_layer(self, layer: QgsVectorLayer):
        '''
        sets a single layer to pick features from

        Parameters
        ----------
        layer : QgsVectorLayer
            the layer containing the features that can be picked
        '''
        if not layer:
            self._layers = []
        else:
            self._layers = [layer]

    def canvasReleaseEvent(self, mouseEvent):
        '''
        override, emit first feature found on mouse release
        '''
        if not self._layers:
            return
        features = QgsMapToolIdentify(self.canvas).identify(
            mouseEvent.x(), mouseEvent.y(), self._layers,
            QgsMapToolIdentify.TopDownStopAtFirst)
        if len(features) > 0:
            self.feature_picked.emit(features[0].mFeature.id())


class FeatureDragger(FeaturePicker):
    '''
    tool for moving features on the map canvas with drag & drop,
    does not change the geometry of the dragged feature but draws a marker
    at the new position and emits the geometry

    Attributes
    ----------
    feature_dragged : pyqtSignal
        emitted when a feature is dragged or clicked on the map canvas,
        (feature id, release position)
    drag_cursor : QCursor
        the appearance of the cursor while dragging a feature
    '''
    feature_dragged = pyqtSignal(int, QgsPointXY)
    drag_cursor = QCursor(Qt.DragMoveCursor)

    def __init__(self, ui_element: QWidget, layers: List[QgsVectorLayer] = [],
                 canvas: QgsMapCanvas = None):
        '''
        Parameters
        ----------
        ui_element : QWidget
            clickable UI element, clicking on it will adctivate/deactivate this
            tool
        layers : list, optional
            the layers containing the features that can be picked,
            defaults to not setting any layers
        canvas : QgsMapCanvas, optional
            the map canvas the tool will work on, defaults to the map canvas of
            the QGIS UI
        '''
        super().__init__(ui_element, layers=layers, canvas=canvas)
        self._marker = None
        self._picked_feature = None
        self._dragging = False

    def reset(self):
        '''
        reset the feature picker to it's initial state
        '''
        self.remove_marker()
        self._picked_feature = None

    def remove_marker(self):
        '''
        remove the marker from the map
        '''
        if not self._marker:
            return
        self.canvas.scene().removeItem(self._marker)
        self._marker = None

    def canvasPressEvent(self, e):
        '''
        override, remember feature on click and move marker (create one if not
        drawn yet)
        '''
        if self._picked_feature is None:
            features = QgsMapToolIdentify(self.canvas).identify(
                e.pos().x(), e.pos().y(), self._layers,
                QgsMapToolIdentify.TopDownStopAtFirst)
            if len(features) == 0:
                return
            feature = features[0].mFeature
            self._picked_feature = feature.id()
        # there is a feature -> drag it
        self._dragging = True
        self.canvas.setCursor(self.drag_cursor)
        # not marked yet -> mark position
        if not self._marker:
            color = QColor(0, 0, 255)
            color.setAlpha(100)
            self._marker = QgsVertexMarker(self.canvas)
            self._marker.setColor(color)
            self._marker.setIconSize(10)
            self._marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self._marker.setPenWidth(10)
        point = self.toMapCoordinates(e.pos())
        self._marker.setCenter(point)

    def canvasMoveEvent(self, e):
        '''
        override, move marker if mouse dragging is active and mouse is moved
        '''
        if not self._marker or not self._dragging:
            return
        # update position of marker while dragging
        point = self.toMapCoordinates(e.pos())
        self._marker.setCenter(point)

    def canvasReleaseEvent(self, mouseEvent):
        '''
        override, emit geometry of position of marker on mouse release
        '''
        self._dragging = False
        if self._picked_feature is None:
            return
        self.canvas.setCursor(self.cursor)
        point = self.toMapCoordinates(self._marker.pos().toPoint())
        self.feature_dragged.emit(self._picked_feature, point)