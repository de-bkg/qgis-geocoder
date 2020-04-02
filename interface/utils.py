from qgis.core import (QgsVectorLayer, QgsProject)

def clone_layer(layer, srs='EPSG:4326', name=None, features=None):
    '''
    clone given layer, adds Point geometry with given srs
    optional names it
    data of new layer is based on all features of origin layer or given features
    '''
    features = features or layer.getFeatures()
    name = name or layer.name() + '__clone'

    clone = QgsVectorLayer(f'Point?crs={srs}', name, 'memory')

    data = clone.dataProvider()
    attr = layer.dataProvider().fields().toList()
    data.addAttributes(attr)
    clone.updateFields()
    data.addFeatures([f for f in features])
    QgsProject.instance().addMapLayer(clone)
    return clone