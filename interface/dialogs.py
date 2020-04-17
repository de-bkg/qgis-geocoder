# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (QDialog, QTableWidgetItem, QAbstractScrollArea,
                                 QLabel, QRadioButton, QHBoxLayout)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt import uic
from qgis.core import (QgsPointXY, QgsGeometry, QgsVectorLayer, QgsFeature,
                       QgsField, QgsProject, QgsCoordinateReferenceSystem,
                       QgsCategorizedSymbolRenderer, QgsRendererCategory,
                       QgsMarkerSymbol, QgsRasterMarkerSymbolLayer)
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
    def __init__(self, layer, feature, results, canvas, review_fields=[],
                 parent=None):
        super().__init__('featurepicker.ui', modal=False, parent=parent)
        self.canvas = canvas
        self.results = results
        self.feature = feature
        self.layer = layer
        self.init_geom = feature.geometry()

        self.populate_review(review_fields)
        self.populate_table()

        self.results_table.selectionModel().currentChanged.connect(
            lambda row, col: self.result_changed(row.data(Qt.UserRole)))
        i = self.feature.attribute('bkg_i')
        if i >= 0:
            self.results_table.selectRow(i)

        self.accept_button.clicked.connect(self.accept)
        self.discard_button.clicked.connect(self.reject)

    def populate_review(self, review_fields):
        for i, field in enumerate(review_fields):
            self.feature_grid.addWidget(QLabel(field), i, 0)
            value = self.feature.attribute(field)
            self.feature_grid.addWidget(QLabel(value), i, 1)

    def populate_table(self):
        columns = ['text', 'score']
        self.results_table.setColumnCount(len(columns))
        for i, column in enumerate(columns):
            self.results_table.setHorizontalHeaderItem(
                i, QTableWidgetItem(column))
        self.results_table.setRowCount(len(self.results))
        for i, result in enumerate(self.results):
            properties = result['properties']
            for j, column in enumerate(columns):
                item = QTableWidgetItem(str(properties[column]))
                item.setData(Qt.UserRole, i)
                self.results_table.setItem(i, j, item)

        self.results_table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        self.results_table.resizeColumnsToContents()

    def result_changed(self, i):
        self.result = self.results[i]
        self.i = i
        coords = self.result['geometry']['coordinates']
        geom = QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1]))
        self.layer.changeGeometry(self.feature.id(), geom)
        self.canvas.refresh()
        self.layer.removeSelection()
        self.layer.select(self.feature.id())
        self.canvas.zoomToSelected(self.layer)

    def accept(self):
        # reset the geometry
        self.layer.changeGeometry(self.feature.id(), self.init_geom)
        super().accept()

    def reject(self):
        self.layer.changeGeometry(self.feature.id(), self.init_geom)
        super().reject()

    def showEvent(self, e):
        # exec() resets the modality
        self.setModal(False)
        self.adjustSize()


class ReverseResultsDialog(Dialog):
    marker_img = 'marker_{}.png'

    def __init__(self, layer, feature, results, canvas, review_fields=[],
                 parent=None):
        super().__init__('reverse_geocoding.ui', modal=False, parent=parent)
        self.canvas = canvas
        self.results = results
        self.feature = feature
        self.layer = layer
        self.accept_button.clicked.connect(self.accept)
        self.geom_only = False
        def geom_only():
            self.geom_only = True
            self.accept()
        self.geom_only_button.clicked.connect(geom_only)
        self.discard_button.clicked.connect(self.reject)

        self.add_results()
        self.populate_review(review_fields)

    def add_results(self):
        self.preview_layer = QgsVectorLayer(
            "Point", "reverse_preview", "memory")

        renderer = QgsCategorizedSymbolRenderer('i')
        for i in range(1, 21):
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
                self.toggle_result(self.results[i], f))

        self.preview_layer.commitChanges()
        extent = self.preview_layer.extent()
        self.canvas.setExtent(extent)
        self.canvas.refresh()
        QgsProject.instance().addMapLayer(self.preview_layer)

    def populate_review(self, review_fields):
        for i, field in enumerate(review_fields):
            self.feature_grid.addWidget(QLabel(field), i, 0)
            value = self.feature.attribute(field)
            self.feature_grid.addWidget(QLabel(value), i, 1)

    def toggle_result(self, result, feature):
        self.preview_layer.removeSelection()
        self.preview_layer.select(feature.id())
        self.result = result

    def result_changed(self, i):
        self.result = self.results[i]
        self.i = i
        coords = self.result['geometry']['coordinates']
        geom = QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1]))
        self.layer.changeGeometry(self.feature.id(), geom)
        self.canvas.refresh()
        self.layer.removeSelection()
        self.layer.select(self.feature.id())
        self.canvas.zoomToSelected(self.layer)

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
