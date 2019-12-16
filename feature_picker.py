from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QDockWidget
from PyQt5.QtGui import QCursor
from qgis.core import QgsVectorLayer, QgsFeature
from qgis.gui import QgsMapToolIdentify
from qgis.PyQt import uic
import os

from .geocode import Result

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'picker_dock.ui'))


class PickerDock(QDockWidget):
    result_set = pyqtSignal(QgsVectorLayer, QgsFeature, Result)

    def __init__(self, canvas, results_cache, parent=None):
        super().__init__("BKG Geocoder Feature Picker")
        self.dlg = PickerUI()
        self.results_cache = results_cache
        self.canvas = canvas
        self.featurePicker = FeaturePicker(self.canvas)
        self.featurePicker.featurePicked.connect(self.featurePicked)
        self.setObjectName("FeaturePickerDock")
        self.setWidget(self.dlg)

        self.dlg.pick_feature_button.clicked.connect(self.select)
        self.dlg.result_list.itemClicked.connect(self.result_changed)

    def clear(self):
        self.dlg.feature_edit.setText('')
        self.dlg.result_list.clear()
        self.dlg.geocode_button.setEnabled(False)

    def select(self):
        self.canvas.setMapTool(self.featurePicker)
        cursor = QCursor(Qt.CrossCursor)
        self.canvas.setCursor(cursor)

    def result_changed(self, item):
        idx = self.dlg.result_list.currentRow()
        self.active_feature.setAttribute('bkg_i', idx)
        result = self.active_results[idx]
        self.result_set.emit(self.active_layer, self.active_feature, result)

    def featurePicked(self, layer, feature):
        self.dlg.geocode_button.setEnabled(True)
        self.active_feature = feature
        self.active_layer = layer
        layer.removeSelection()
        layer.select(feature.id())
        attr = []
        attributes = feature.attributes()
        res_idx = 0
        for field in layer.fields():
            field_name = field.name()
            if not field_name.startswith('bkg_'):
                idx = feature.fieldNameIndex(field_name)
                value = attributes[idx]
                attr.append(value)
            if field_name == 'bkg_i':
                idx = feature.fieldNameIndex(field_name)
                res_idx = attributes[idx]
        feat_repr = '({l}) Feature {id} - {a}'.format(
            id=feature.id(), a=', '.join(map(str, attr)), l=layer.name())
        self.dlg.feature_edit.setText(feat_repr)
        self.dlg.feature_edit.setToolTip(feat_repr)
        self.dlg.result_list.clear()
        results = self.results_cache.get(layer, feature.id())
        if results:
            self.active_results = results
            for result in results:
                self.dlg.result_list.addItem(str(result))
            self.dlg.result_list.setCurrentRow(res_idx)


class PickerUI(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)


class FeaturePicker(QgsMapToolIdentify):
    featurePicked = pyqtSignal(QgsVectorLayer, QgsFeature)

    def canvasReleaseEvent(self, mouseEvent):
        results = self.identify(mouseEvent.x(), mouseEvent.y(),
                                self.LayerSelection, self.VectorLayer)
        if len(results) > 0:
            self.featurePicked.emit(results[0].mLayer,
                                    QgsFeature(results[0].mFeature))
