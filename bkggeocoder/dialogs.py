# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer, QVariant, QObject
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtGui import QTextCursor
from qgis.PyQt import uic
import os
import datetime
from .geocode import GeocodeWorker, Results

UI_PATH = os.path.join(os.path.dirname(__file__), 'ui')


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


class FeaturePickerDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('featurepicker.ui', modal=False, parent=parent)


class ProgressDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__('progress.ui', modal=True, parent=parent)
        self.close_button.clicked.connect(self.close)

#class ProgressDialog(QDialog, FORM_CLASS):
    #"""
    #Dialog showing progress in textfield and bar after starting a certain task with run()
    #"""
    #def __init__(self, worker, parent=None, auto_close=False, auto_run=False):
        #super().__init__(parent=parent)
        #self.parent = parent
        #self.setupUi(self)
        #self.setAttribute(Qt.WA_DeleteOnClose)
        #self.progress_bar.setValue(0)
        #self.close_button.clicked.connect(self.close)
        #self.stop_button.setVisible(False)
        #self.close_button.setVisible(False)
        #self.auto_close = auto_close

        #self.worker = worker
        #self.thread = QThread(self.parent)
        #self.worker.moveToThread(self.thread)

        #self.thread.started.connect(self.worker.run)
        #self.worker.finished.connect(self.finished)
        #self.worker.error.connect(self.show_status)
        #self.worker.message.connect(self.show_status)
        #self.worker.counter.connect(self.progress)

        #self.start_button.clicked.connect(self.run)
        #self.stop_button.clicked.connect(self.stop)
        #self.close_button.clicked.connect(self.close)

        #self.timer = QTimer(self)
        #self.timer.timeout.connect(self.update_timer)
        #if auto_run:
            #self.run()

    #def running(self):
        #self.close_button.setVisible(True)
        #self.cancelButton.setText('Stoppen')
        #self.cancelButton.clicked.disconnect(self.close)

    #def finished(self):
        ## already gone if killed
        #try:
            #self.worker.deleteLater()
        #except:
            #pass
        #self.thread.quit()
        #self.thread.wait()
        #self.thread.deleteLater()
        #self.timer.stop()
        #self.close_button.setVisible(True)
        #self.stop_button.setVisible(False)
        #if self.auto_close:
            #self.close()

    #def show_status(self, text):
        #self.log_edit.appendHtml(text)
        ##self.log_edit.moveCursor(QTextCursor.Down)
        #scrollbar = self.log_edit.verticalScrollBar()
        #scrollbar.setValue(scrollbar.maximum());

    #def progress(self, progress, obj=None):
        #if isinstance(progress, QVariant):
            #progress = progress.toInt()[0]
        #self.progress_bar.setValue(progress)

    #def start_timer(self):
        #self.start_time = datetime.datetime.now()
        #self.timer.start(1000)

    ## task needs to be overridden
    #def run(self):
        #self.start_timer()
        #self.stop_button.setVisible(True)
        #self.start_button.setVisible(False)
        #self.thread.start()

    #def stop(self):
        #self.timer.stop()
        #self.worker.kill()
        #self.log_edit.appendHtml('<b> Vorgang abgebrochen </b> <br>')
        #self.log_edit.moveCursor(QTextCursor.End)
        #self.finished()

    #def update_timer(self):
        #delta = datetime.datetime.now() - self.start_time
        #h, remainder = divmod(delta.seconds, 3600)
        #m, s = divmod(remainder, 60)
        #timer_text = '{:02d}:{:02d}:{:02d}'.format(h, m, s)
        #self.elapsed_time_label.setText(timer_text)


#class GeocodeProgressDialog(ProgressDialog):
    #'''
    #dialog showing progress on threaded geocoding
    #'''
    #feature_done = pyqtSignal(int, Results)

    #def __init__(self, geocoder, layer, field_map, on_progress,
                 #on_done, feature_ids=None, parent=None, area_wkt=None):
        #queries = []
        #features = layer.getFeatures(feature_ids) if feature_ids \
            #else layer.getFeatures()

        #for feature in features:
            #args, kwargs = field_map.to_args(feature)
            #if area_wkt:
                #kwargs['geometry'] = area_wkt
            #queries.append((feature.id(), (args, kwargs)))

        #worker = GeocodeWorker(geocoder, queries)
        #worker.feature_done.connect(on_progress)
        #worker.finished.connect(on_done)
        #super().__init__(worker, parent=parent, auto_run=True)





