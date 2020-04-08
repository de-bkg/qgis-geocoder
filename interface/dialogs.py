# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QAbstractScrollArea
from qgis.PyQt import uic
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
                self.results_table.setItem(
                    i, j, QTableWidgetItem(str(properties[column])))
        self.results_table.setSizeAdjustPolicy(
            QAbstractScrollArea.AdjustToContents)
        self.results_table.resizeColumnsToContents()

    def showEvent(self, e):
        self.adjustSize()

    #def clear(self):
        #self.dlg.feature_edit.setText('')
        #self.dlg.result_list.clear()
        #self.dlg.geocode_button.setEnabled(False)

    #def select(self):
        #self.canvas.setMapTool(self.featurePicker)
        #cursor = QCursor(Qt.CrossCursor)
        #self.canvas.setCursor(cursor)

    #def result_changed(self, item):
        #idx = self.dlg.result_list.currentRow()
        #self.active_feature.setAttribute('bkg_i', idx)
        #result = self.active_results[idx]
        #self.result_set.emit(self.active_layer, self.active_feature, result)

    #def featurePicked(self, layer, feature):
        #self.dlg.geocode_button.setEnabled(True)
        #self.active_feature = feature
        #self.active_layer = layer
        #layer.removeSelection()
        #layer.select(feature.id())
        #attr = []
        #attributes = feature.attributes()
        #res_idx = 0
        #for field in layer.fields():
            #field_name = field.name()
            #if not field_name.startswith('bkg_'):
                #idx = feature.fieldNameIndex(field_name)
                #value = attributes[idx]
                #attr.append(value)
            #if field_name == 'bkg_i':
                #idx = feature.fieldNameIndex(field_name)
                #res_idx = attributes[idx]
        #feat_repr = '({l}) Feature {id} - {a}'.format(
            #id=feature.id(), a=', '.join(map(str, attr)), l=layer.name())
        #self.dlg.feature_edit.setText(feat_repr)
        #self.dlg.feature_edit.setToolTip(feat_repr)
        #self.dlg.result_list.clear()
        #results = self.results_cache.get(layer, feature.id())
        #if results:
            #self.active_results = results
            #for result in results:
                #self.dlg.result_list.addItem(str(result))
            #self.dlg.result_list.setCurrentRow(res_idx)

