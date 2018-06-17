from dbscan_smote import DBSCANSMOTE
from kmeans_smote import KMeansSMOTE

class ClusteringOverSampler(KMeansSMOTE,DBSCANSMOTE):

    def __init__(self):
        #super(Cluver, self).__init__()
        super().__init__()
        
