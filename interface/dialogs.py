# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (QDialog, QTableWidgetItem, QAbstractScrollArea,
                                 QLabel, QRadioButton, QHBoxLayout)
                                 #QGraphicsPixmapItem)
#from qgis.PyQt.QtGui import QPixmap
#from qgis.PyQt.QtCore import Qt, QPointF
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt import uic
from qgis.core import (QgsPointXY, QgsGeometry, QgsVectorLayer, QgsFeature,
                       QgsField, QgsProject, QgsCoordinateReferenceSystem)
import os

from config import UI_PATH, ICON_PATH, Config

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

    def closeEvent(self, e):
        # reset the geometry
        self.layer.changeGeometry(self.feature.id(), self.init_geom)

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
        self.init_geom = feature.geometry()

        self.populate_review(review_fields)
        self.populate_frame()
        self.add_preview_layer()

    def add_preview_layer(self):
        self.preview_layer = QgsVectorLayer(
            "Point", "reverse_preview", "memory")

        crs = QgsCoordinateReferenceSystem(config.projection)
        self.preview_layer.setCrs(crs)
        self.preview_layer.startEditing()

        provider = self.preview_layer.dataProvider()
        provider.addAttributes([
            QgsField('i',  QVariant.Int),
            QgsField('text', QVariant.String)
        ])

        for i, result in enumerate(self.results):
            feature = QgsFeature()
            coords = result['geometry']['coordinates']
            geom = QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1]))
            feature.setGeometry(geom)
            feature.setAttributes([i + 1, result['properties']['text'],])
            provider.addFeature(feature)

        self.preview_layer.commitChanges()
        QgsProject.instance().addMapLayer(self.preview_layer)

    def populate_review(self, review_fields):
        for i, field in enumerate(review_fields):
            self.feature_grid.addWidget(QLabel(field), i, 0)
            value = self.feature.attribute(field)
            self.feature_grid.addWidget(QLabel(value), i, 1)

    def populate_frame(self):
        layout = self.results_frame.layout()

        for i, result in enumerate(self.results):
            properties = result['properties']
            radio = QRadioButton(properties['text'])
            hlayout = QHBoxLayout()
            hlayout.addWidget(radio)
            layout.addLayout(hlayout)

    #def draw_markers(self):
        #scene = self.canvas.scene()
        #self.markers = []
        #for i, result in enumerate(self.results):
            #img_path = os.path.join(ICON_PATH, self.marker_img.format(i))
            #if not os.path.exists(img_path):
                #continue
            #image = QPixmap(img_path)
            #marker = QGraphicsPixmapItem(image)
            #self.markers.append(marker)
            #point = QPointF(50, 50)
            #point_item = marker.mapFromScene(point)
            #marker.setPos(point_item)
            #scene.addItem(marker)

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

    def closeEvent(self, e):
        # reset the geometry
        self.layer.changeGeometry(self.feature.id(), self.init_geom)

    def showEvent(self, e):
        # exec() resets the modality
        self.setModal(False)
        self.adjustSize()
