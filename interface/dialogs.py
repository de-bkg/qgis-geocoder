# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (QDialog, QTableWidgetItem, QAbstractScrollArea,
                                 QLabel, QRadioButton, QHBoxLayout)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt import uic
from qgis.core import (QgsPointXY, QgsGeometry, QgsVectorLayer, QgsFeature,
                       QgsField, QgsProject, QgsCoordinateReferenceSystem,
                       QgsCategorizedSymbolRenderer, QgsRendererCategory,
                       QgsMarkerSymbol, QgsRasterMarkerSymbolLayer,
                       QgsRectangle)
import os

from config import UI_PATH, STYLE_PATH, Config, ICON_PATH

config = Config()


class Dialog(QDialog):
    def __init__(self, ui_file=None, modal=True, parent=None, title=None):
        super().__init__(parent=parent)
        if title:
            self.setWindowTitle(title)

        if ui_file:
            # look for file ui folder if not found
            ui_file = ui_file if os.path.exists(ui_file) \
                else os.path.join(UI_PATH, ui_file)
            uic.loadUi(ui_file, self)
        self.setModal(modal)
        self.setupUi()

    def setupUi(self):
        pass

    def show(self):
        return self.exec_()


class SaveCSVDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('save_csv.ui', modal=True, parent=parent)


class OpenCSVDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('open_csv.ui', modal=True, parent=parent)


class ProgressDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('progress.ui', modal=True, parent=parent)
        self.close_button.clicked.connect(self.close)


class InspectResultsDialog(Dialog):
    ui_file = 'featurepicker.ui'
    marker_img = 'marker_{}.png'

    def __init__(self, feature, results, canvas, review_fields=[], preselect=-1,
                 parent=None):
        super().__init__(self.ui_file, modal=False, parent=parent)
        self.canvas = canvas
        self.results = results
        self.feature = feature
        self.geom_only_button.setVisible(False)
        self.result = None
        self.i = -1

        self.populate_review(review_fields)
        self.add_results(preselect=preselect)

        self.accept_button.clicked.connect(self.accept)
        self.discard_button.clicked.connect(self.reject)

    def populate_review(self, review_fields):
        for i, field in enumerate(review_fields):
            self.feature_grid.addWidget(QLabel(field), i, 0)
            value = self.feature.attribute(field)
            self.feature_grid.addWidget(QLabel(value), i, 1)

    def add_results(self, preselect=-1):
        self.preview_layer = QgsVectorLayer("Point", "results_tmp", "memory")

        renderer = QgsCategorizedSymbolRenderer('i')
        for i in range(1, len(self.results) + 1):
            category = QgsRendererCategory()
            category.setValue(i)
            symbol = QgsMarkerSymbol.createSimple({'color': 'white'})
            img_path = os.path.join(ICON_PATH, f'marker_{i}.png')
            if os.path.exists(img_path):
                symbol_layer = QgsRasterMarkerSymbolLayer()
                symbol_layer.setPath(img_path)
                symbol.appendSymbolLayer(symbol_layer)
            category.setSymbol(symbol)
            renderer.addCategory(category)
        self.preview_layer.setRenderer(renderer)

        crs = QgsCoordinateReferenceSystem(config.projection)
        self.preview_layer.setCrs(crs)
        self.preview_layer.startEditing()
        provider = self.preview_layer.dataProvider()
        provider.addAttributes([
            QgsField('i',  QVariant.Int),
            QgsField('text', QVariant.String)
        ])

        layout = self.results_frame.layout()

        for i, result in enumerate(self.results):
            feature = QgsFeature()
            coords = result['geometry']['coordinates']
            geom = QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1]))
            feature.setGeometry(geom)
            feature.setAttributes([i + 1, result['properties']['text'],])
            provider.addFeature(feature)

            properties = result['properties']
            radio = QRadioButton(properties['text'])
            hlayout = QHBoxLayout()
            preview = QLabel()
            hlayout.addWidget(preview)
            hlayout.addWidget(radio)
            preview.setMaximumWidth(20)
            preview.setMinimumWidth(20)
            img_path = os.path.join(ICON_PATH, f'marker_{i+1}.png')
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                preview.setPixmap(pixmap.scaled(
                    preview.size(), Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))
            layout.addLayout(hlayout)

            radio.toggled.connect(
                lambda c, i=i, f=feature:
                self.toggle_result(self.results[i], f, i=i))
            if i == preselect:
                radio.setChecked(True)

        self.preview_layer.commitChanges()
        extent = self.preview_layer.extent()
        self.canvas.setExtent(extent)
        self.canvas.refresh()
        QgsProject.instance().addMapLayer(self.preview_layer)

    def toggle_result(self, result, feature, i=0):
        self.result = self.results[i]
        self.i = i
        self.preview_layer.removeSelection()
        self.preview_layer.select(feature.id())
        self.result = result

        # center map on point
        point = feature.geometry().asPoint()
        rect = QgsRectangle(point, point)
        self.canvas.setExtent(rect)
        self.canvas.refresh()

    def accept(self):
        QgsProject.instance().removeMapLayers([self.preview_layer.id()])
        super().accept()

    def reject(self):
        QgsProject.instance().removeMapLayers([self.preview_layer.id()])
        super().reject()

    def showEvent(self, e):
        # exec() resets the modality
        self.setModal(False)
        self.adjustSize()


class ReverseResultsDialog(InspectResultsDialog):

    def __init__(self, feature, results, canvas, review_fields=[],
                 parent=None, preselect=0):
        super().__init__(feature, results, canvas,
                         review_fields=review_fields, parent=parent)
        self.results_label.setText('Nächstgelegene Adressen')
        self.accept_button.setText('Adresse und Koordinaten übernehmen')
        self.geom_only_button.setVisible(True)
        self.geom_only = False
        def geom_only():
            self.geom_only = True
            self.accept()
        self.geom_only_button.clicked.connect(geom_only)

