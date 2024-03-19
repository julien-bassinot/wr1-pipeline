# wr1-pipeline

## Installation de docker engine, minikube, minio et argo

**Disclaimer:** L'installation a été testé sur un Linux Ubuntu 22.04

Installer docker engine 24 ([ne pas installer la dernière version](https://github.com/kubernetes/minikube/issues/18021))
<br>https://docs.docker.com/engine/install/

Suivre ce tutorial pour continuer les installations:<br>
https://blog.devgenius.io/unleash-your-pipeline-creativity-local-development-with-argo-workflows-and-minio-on-minikube-7537642b7b1d


Pendant le tutoriel:
* penser à démarrer ```minikube tunnel``` juste après ```minikube start```
* utiliser un LoadBalancer plutôt qu'un Ingress pour Minio et [Argo](https://argo-workflows.readthedocs.io/en/latest/quick-start/#submit-via-the-ui)


Une fois les installations faites, les services peuvent se lancer avec les commandes suivantes (éventuellement dans
plusieurs bash):
```shell
minikube start
minikube tunnel
minikube service minio-service -n argo
kubectl -n argo port-forward deployment/argo-server 2746:2746
```


## Création des images docker

Pour utiliser la registry de minikube, il faut activer les addons:
```shell
minikube addons enable registry
```
Puis lancer cette commande (à relancer à chaque redémarrage):
```shell
kubectl -n kube-system port-forward service/registry 5000:80
```


Ensuite on peut construire les image `orfeo` à partir de `ndpi/Dockerfile` et osgeo à partir de 
`waterSurf_Mask/Dockerfile`, les tagger et les pousser dans minikube.
```shell
cd ndpi
sudo docker build -t orfeo:latest .
docker tag orfeo:latest localhost:5000/orfeo:latest
docker push localhost:5000/orfeo:latest
```

```shell
cd waterSurf_Mask
sudo docker build -t osgeo:latest .
docker tag osgeo:latest localhost:5000/osgeo:latest
docker push localhost:5000/osgeo:latest
```

```shell
cd vectorize
sudo docker build -t riogeo:latest
docker tag riogeo:latest localhost:5000/riogeo:latest
docker push localhost:5000/riogeo:latest
```

L'image orfeo permet d'utiliser la librairie [OTB](https://www.orfeo-toolbox.org/CookBook/index.html) tandis que l'image
osgeo permet d'exécuter du code de la librairie [gdal](https://gdal.org/programs/index.html). L'image riogeo contient les bibliothèques rioxarray, 
geopandas et opencv.


## Lancement de la pipeline Argo-Workflows

* Charger les images B4 et B8 par sous dossier dans le bucket S3: <br>
`argo-bucket/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B4.tif
`<br>
`argo-bucket/input/SENTINEL2A_20210115-105852-555_L2A_T31TCJ/SENTINEL2A_20210115-105852-555_L2A_T31TCJ_C_V2-2_FRE_B8.tif
`

* Copier les images 12 fois pour qu'il y ait un dossier par mois sur l'année 2021, changez à chaque fois l'année dans le
nom des fichiers.

* Créer un dossier `argo-bucket/output` dans le bucket S3


Ensuite dans un terminal lancez la commande:
```shell
argo submit -n argo --watch wr1-v2.yaml
```


Observer l'état de la pipeline sur l'interface utilisateur d'Argo à l'adresse https://localhost:2746/

Les résultats sont stockés dans `argo-bucket/output`



## To-do list
- [x] Ajouter la partie vectorisation
- [ ] Choisir le nombre de pods max à lancer avec `parallelism`, passer en dag si besoin.
- [ ] Utiliser les fichiers zippés super-résolution à 5m. Adapter la taille du PV.
- [ ] Remplacer les persistentVolumeClaim par des artifacts. Tester les deux versions en terme de coût / rapidité.
