from qgis import utils
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QCursor, QColor
from qgis.gui import (QgsMapToolEmitPoint, QgsMapToolIdentify, QgsVertexMarker)
from qgis.core import (QgsFeature, QgsGeometry, QgsPointXY)


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
    feature_picked = pyqtSignal(int)

    def __init__(self, ui_element, layers=[], canvas=None, draw_marker=False):
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
            self.feature_picked.emit(features[0].mFeature.id())


class FeatureDragger(FeaturePicker):
    feature_dragged = pyqtSignal(int, QgsPointXY)
    drag_cursor = QCursor(Qt.DragMoveCursor)

    def __init__(self, ui_element, layers=[], canvas=None):
        super().__init__(ui_element, layers=layers, canvas=canvas)
        self.marker = None
        self.picked_feature = None
        self.dragging = False

    def reset(self):
        self.remove_marker()
        self.picked_feature = None

    def remove_marker(self):
        if not self.marker:
            return
        self.canvas.scene().removeItem(self.marker)
        self.marker = None

    def canvasPressEvent(self, e):
        if self.picked_feature is None:
            features = QgsMapToolIdentify(self.canvas).identify(
                e.pos().x(), e.pos().y(), self._layers,
                QgsMapToolIdentify.TopDownStopAtFirst)
            if len(features) == 0:
                return
            self.picked_feature = features[0].mFeature.id()
        # there is a feature -> drag it
        self.dragging = True
        self.canvas.setCursor(self.drag_cursor)
        # not marked yet -> mark position
        if not self.marker:
            color = QColor(0, 0, 255)
            color.setAlpha(100)
            self.marker = QgsVertexMarker(self.canvas)
            self.marker.setColor(color)
            self.marker.setIconSize(10)
            self.marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.marker.setPenWidth(10)
        point = self.toMapCoordinates(e.pos())
        self.marker.setCenter(point)

    def canvasMoveEvent(self, e):
        if not self.marker or not self.dragging:
            return
        # update position of marker while dragging
        point = self.toMapCoordinates(e.pos())
        self.marker.setCenter(point)

    def canvasReleaseEvent(self, mouseEvent):
        self.dragging = False
        if self.picked_feature is None:
            return
        self.canvas.setCursor(self.cursor)
        point = self.toMapCoordinates(self.marker.pos().toPoint())
        self.feature_dragged.emit(self.picked_feature, point)
