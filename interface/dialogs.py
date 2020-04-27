# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (QDialog, QLabel, QRadioButton, QGridLayout,
                                 QFrame)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt import uic
from qgis.core import (QgsPointXY, QgsGeometry, QgsVectorLayer, QgsFeature,
                       QgsField, QgsProject,
                       QgsCategorizedSymbolRenderer, QgsRendererCategory,
                       QgsMarkerSymbol, QgsRasterMarkerSymbolLayer,
                       QgsRectangle, QgsCoordinateTransform)
import os

from interface.utils import clear_layout
from config import UI_PATH, Config, ICON_PATH

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
    show_score = True

    def __init__(self, feature, results, canvas, review_fields=[], preselect=-1,
                 crs='EPSG:4326', parent=None):
        super().__init__(self.ui_file, modal=False, parent=parent)
        self.canvas = canvas
        self.results = results
        self.feature = feature
        self.geom_only_button.setVisible(False)
        self.result = None
        self.i = -1
        self.crs = crs

        self.populate_review(review_fields)
        self.setup_preview_layer()
        self.add_results(preselect=preselect)

        self.accept_button.clicked.connect(self.accept)
        self.discard_button.clicked.connect(self.reject)

    def populate_review(self, review_fields):
        if review_fields:
            headline = QLabel('Geokodierungs-Parameter')
            font = headline.font()
            font.setUnderline(True)
            headline.setFont(font)
            self.review_layout.addWidget(headline)
            grid = QGridLayout()
            for i, field in enumerate(review_fields):
                grid.addWidget(QLabel(field), i, 0)
                value = self.feature.attribute(field)
                grid.addWidget(QLabel(value), i, 1)
            self.review_layout.addLayout(grid)
            # horizontal line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            self.review_layout.addWidget(line)

        headline = QLabel('Anschrift laut Dienst')
        font = headline.font()
        font.setUnderline(True)
        headline.setFont(font)
        self.review_layout.addWidget(headline)
        bkg_text = self.feature.attribute('bkg_text')
        self.review_layout.addWidget(QLabel(bkg_text))

    def setup_preview_layer(self):
        self.preview_layer = QgsVectorLayer(
            f'Point?crs={self.crs}', 'results_tmp', 'memory')

        renderer = QgsCategorizedSymbolRenderer('i')
        for i in range(1, len(self.results) + 1):
            category = QgsRendererCategory()
            category.setValue(i)
            symbol = QgsMarkerSymbol.createSimple({'color': 'white'})
            img_path = os.path.join(ICON_PATH, f'marker_{i}.png')
            if os.path.exists(img_path):
                symbol_layer = QgsRasterMarkerSymbolLayer()
                symbol_layer.setPath(img_path)
                symbol_layer.setSize(5)
                symbol.appendSymbolLayer(symbol_layer)
            category.setSymbol(symbol)
            renderer.addCategory(category)
        self.preview_layer.setRenderer(renderer)

        self.preview_layer.startEditing()
        provider = self.preview_layer.dataProvider()
        provider.addAttributes([
            QgsField('i',  QVariant.Int),
            QgsField('text', QVariant.String)
        ])
        QgsProject.instance().addMapLayer(self.preview_layer)

    def add_results(self, preselect=-1, row_number=0):

        provider = self.preview_layer.dataProvider()

        for i, result in enumerate(self.results):
            feature = QgsFeature()
            coords = result['geometry']['coordinates']
            geom = QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1]))
            feature.setGeometry(geom)
            feature.setAttributes([i + 1, result['properties']['text'],])
            provider.addFeature(feature)

            properties = result['properties']
            radio = QRadioButton(properties['text'])

            preview = QLabel()
            preview.setMaximumWidth(20)
            preview.setMinimumWidth(20)
            self.results_contents.addWidget(preview, i+row_number, 0)
            self.results_contents.addWidget(radio, i+row_number, 1)
            if self.show_score:
                score = QLabel(f'Score {properties["score"]}')
                self.results_contents.addWidget(score, i+row_number, 2)
            img_path = os.path.join(ICON_PATH, f'marker_{i+1}.png')
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                preview.setPixmap(pixmap.scaled(
                    preview.size(), Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))

            radio.toggled.connect(
                lambda c, i=i, f=feature:
                self.toggle_result(self.results[i], f, i=i))
            if i == preselect:
                radio.setChecked(True)

        self.preview_layer.commitChanges()
        extent = self.preview_layer.extent()
        transform = QgsCoordinateTransform(
            self.preview_layer.crs(),
            self.canvas.mapSettings().destinationCrs(),
            QgsProject.instance()
        )
        self.canvas.setExtent(transform.transform(extent))
        self.canvas.refresh()

    def toggle_result(self, result, feature, i=0):
        self.result = self.results[i]
        self.i = i
        self.preview_layer.removeSelection()
        self.preview_layer.select(feature.id())
        self.result = result
        self.zoom_to(feature)

    def zoom_to(self, feature):
        # center map on point
        point = feature.geometry().asPoint()
        rect = QgsRectangle(point, point)
        transform = QgsCoordinateTransform(
            self.preview_layer.crs(),
            self.canvas.mapSettings().destinationCrs(),
            QgsProject.instance()
        )
        self.canvas.setExtent(transform.transform(rect))
        self.canvas.refresh()

    def accept(self):
        QgsProject.instance().removeMapLayer(self.preview_layer.id())
        super().accept()

    def reject(self):
        QgsProject.instance().removeMapLayer(self.preview_layer.id())
        super().reject()

    def showEvent(self, e):
        # exec() resets the modality
        self.setModal(False)
        self.adjustSize()


class ReverseResultsDialog(InspectResultsDialog):
    show_score = False

    def __init__(self, feature, results, canvas, review_fields=[],
                 parent=None, preselect=-1, crs='EPSG:4326'):
        super().__init__(feature, results, canvas, crs=crs, preselect=preselect,
                         review_fields=review_fields, parent=parent)
        self.results_label.setText('Nächstgelegene Adressen')
        self.setWindowTitle('Nachbaradresssuche')
        self.accept_button.setText('Adresse und Koordinaten übernehmen')
        self.geom_only_button.setVisible(True)
        self.geom_only = False
        def geom_only():
            self.geom_only = True
            self.accept()
        self.geom_only_button.clicked.connect(geom_only)

    def add_results(self, preselect=-1):
        # add a radio button for

        point = self.feature.geometry().asPoint()
        radio_label = ('Koordinaten der Markierung '
                       f'({round(point.x(), 2)}, {round(point.y(), 2)})')
        radio = QRadioButton(radio_label)
        def toggled(checked):
            # radio is checked -> no result selected
            if checked:
                self.result = None
                self.i = -1
                self.preview_layer.removeSelection()
                self.zoom_to(self.feature)
            self.accept_button.setDisabled(checked)
        radio.toggled.connect(toggled)
        # initially this option is checked
        radio.setChecked(True)

        self.results_contents.addWidget(radio, 0, 1)
        super().add_results(preselect=-1, row_number=1)

    def update_results(self, results):
        self.results = results
        # lazy way to reset preview
        QgsProject.instance().removeMapLayer(self.preview_layer.id())
        clear_layout(self.results_contents)
        self.setup_preview_layer()
        self.add_results()

