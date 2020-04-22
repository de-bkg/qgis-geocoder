from qgis import utils
from qgis.PyQt.QtCore import pyqtSignal, Qt, QTimer
from qgis.PyQt.QtGui import QCursor
from qgis.gui import (QgsMapToolEmitPoint, QgsMapToolIdentify)
from qgis.PyQt.QtWidgets import QToolTip
from qgis.core import (QgsFeature, QgsCoordinateTransform, QgsGeometry,
                       QgsProject, QgsCoordinateReferenceSystem)


class MapTool:
    '''
    abstract class for tools triggered by clicking a certain ui element
    '''
    cursor = QCursor(Qt.CrossCursor)

    def __init__(self, ui_element, canvas=None):
        self.ui_element = ui_element
        self.canvas = canvas or utils.iface.mapCanvas()
        self.ui_element.clicked.connect(
            lambda checked: self.set_active(checked))

    def set_active(self, active):
        if active:
            self.canvas.setMapTool(self)
            self.canvas.mapToolSet.connect(self.disconnect)
            self.canvas.setCursor(self.cursor)
        else:
            self.canvas.unsetMapTool(self)
            self.ui_element.blockSignals(True)
            self.ui_element.setChecked(False)
            self.ui_element.blockSignals(False)

    def disconnect(self, **kwargs):
        self.canvas.mapToolSet.disconnect(self.disconnect)
        self.set_active(False)


class MapClickedTool(MapTool, QgsMapToolEmitPoint):
    map_clicked = pyqtSignal(QgsGeometry)

    def __init__(self, ui_element, target_epsg=25832, canvas=None):
        MapTool.__init__(self, ui_element, target_epsg=target_epsg,
                         canvas=canvas)
        QgsMapToolEmitPoint.__init__(self, canvas=self.canvas)
        self.canvasClicked.connect(self._map_clicked)

    def _map_clicked(self, point, e):
        geom = QgsGeometry.fromPointXY(point)
        self.map_clicked.emit(self.transform_from_map(geom))


class FeaturePicker(MapTool, QgsMapToolEmitPoint):
    feature_picked = pyqtSignal(QgsFeature)

    def __init__(self, ui_element, layers=[], canvas=None):
        MapTool.__init__(self, ui_element, canvas=canvas)
        QgsMapToolEmitPoint.__init__(self, canvas=self.canvas)
        self._layers = layers

    def add_layer(self, layer):
        if layer:
            self._layers.append(layer)

    def set_layer(self, layer):
        if not layer:
            self._layers = []
        else:
            self._layers = [layer]

    def canvasReleaseEvent(self, mouseEvent):
        if not self._layers:
            return
        features = QgsMapToolIdentify(self.canvas).identify(
            mouseEvent.x(), mouseEvent.y(), self._layers,
            QgsMapToolIdentify.TopDownStopAtFirst)
        if len(features) > 0:
            self.feature_picked.emit(features[0].mFeature)