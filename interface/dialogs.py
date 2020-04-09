# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QAbstractScrollArea
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import uic
from qgis.core import QgsPointXY, QgsGeometry
import os

from config import UI_PATH


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


class ReverseGeocodingDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('reverse_geocoding.ui', modal=False, parent=parent)


class ProgressDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('progress.ui', modal=True, parent=parent)
        self.close_button.clicked.connect(self.close)


class InspectResultsDialog(Dialog):
    def __init__(self, layer, feature, results, canvas, parent=None):
        super().__init__('featurepicker.ui', modal=False, parent=parent)
        self.canvas = canvas
        self.results = results
        self.feature = feature
        self.layer = layer

        self.populate_table()
        self.accept_button.clicked.connect(self.accept)
        self.discard_button.clicked.connect(self.reject)

        self.init_geom = feature.geometry()

        self.results_table.selectionModel().currentChanged.connect(
            lambda row, col: self.result_changed(row.data(Qt.UserRole)))
        i = self.feature.attribute('bkg_i')
        self.results_table.selectRow(i)

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
