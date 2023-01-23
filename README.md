# veolia-idf
Ce script automatise le chargement de l'historique de votre consommation d'eau récupéré sur le site de Veolia Ile-de-France dans les solutions domotiques :
 - [Domoticz](https://domoticz.com/)
 - [Home Assistant](https://www.home-assistant.io/)

Ce script s'installe sur le serveur domotique ou sur autre serveur. Son exécution est manuelle ou peut se planifier à travers un planificateur de tâche tel que "cron".

La récupération des données se fait grâce à l'outil `selenium` et l'exécution en mode Headless de Firefox ou Chromium (simulation d'un utilisateur en tâche de fond sans mode graphique).

## Fonctionnalités :
* Récupération et chargement de l'intégralité de l'historique
* Gestion multi-contrat
* Vérification de l'intégrité de l'environnement (prérequis / configuration sur serveur domotique)
* Mode débugue graphique
* Possible intégration avec d'autre solution domotique (à vous de jouer)

## Prérequis :
* `firefox`+`geckodriver` OU `chromium`+`chromium-driver`
* python 3
* xvfb
* xephyr (recommandé)
* modules python :
  * selenium
  * pyvirtualdisplay
  * colorama
  * urllib3
  * qq autres... (le script commence par vérifier la présence des modules)
* Un Virtual Sensor Domoticz

## Exemple d'installation des prérequis sur Ubuntu 20.04 :
```shell
apt install firefox firefox-geckodriver xvfb xserver-xephyr python3-selenium python3-pyvirtualdisplay python3-colorama python3-urllib3
```

## Création du "Virtual Sensor" sur Domoticz :
* Créer un Matériel de Type "Dummy" -> Domoticz / Setup / Hardware / Dummy
* Créer un "Virtual Sensor" de type : "Managed Counter"
* Configurer le sensor -> Domoticz / Utility / [Bouton "edit" de votre sensor]
  * Type Counter : water
  * Counter Divider : 1000
  * Meter Offset : 0

## Domoticz

### Installation :

Copier les fichiers `veolia-idf-domoticz.py` et `config.json.exemple` sur votre serveur. Comme par exemple avec ces commandes :
```shell
mkdir -p /opt
cd /opt
git clone https://github.com/s0nik42/veolia-idf
cd veolia-idf
```
Pour mettre à jour :
```shell
git pull
```
Donnez la permission d'exécution si vous êtes sous Linux :
```shell
chmod ugo+x veolia-idf-domoticz.py
```
Ajouter les prérequis python3 :
```shell
pip3 install -r requirements.txt
```

### Configuration :
Copier le fichier `config.json.exemple` en `config.json`
```shell
cp config.json.exemple config.json
```
Modifier le contenu du fichier avec vos valeurs. les champs obligatoires sont :

* "veolia_login": votre login de connexion sur le site https://espace-client.vedif.eau.veolia.fr/
* "veolia_password": votre mot de passe
* "veolia_contract": votre numero de contrat (se trouve sur le site ou une facture)
* "domoticz_server": url du server Domoticz (genre : http://127.0.0.1:8080/)
* "domoticz_idx": le numero du "virtual sensor" Domoticz crée (se trouve dans : Domoticz/Devices/[Colonne Idx]

## Home Assistant

Voir [le forum HACF](https://forum.hacf.fr/t/veolia-idf-sedif-consommation-eau-potable-suivi-consommation/11492) pour les instructions.

## Paramétrer votre système pour le mode débogue (optionnel, mais recommandé)

Si vous rencontrez des problèmes à l'exécution, regardez dans un premier temps le fichier "veolia.log".

Si cela ne suffit pas, pour aller plus loin il sera utile d'utiliser le mode débogue (option `--debug`).

Dans ce dernier cas il y a 3 scenarios :

1. Le script est exécuté en locale par l'utilisateur avec lequel vous êtes logués  ==> ca devrait fonctionner tout seul, mais vous devez utiliser une machine de type "Linux" avec interface graphique ;
2. Vous exécutez le script sur une machine distante Linux. Il convient alors de vérifier que la commande suivante fonctionne après être connecté sur la machine Linux distante (via `ssh` probablement) :
`xlogo`;
3. Vous êtes sous Windows, vous pouvez par exemple utiliser la solution [Docker](https://www.docker.com/) un serveur X (p.e. [VcXsvr](https://sourceforge.net/projects/vcxsrv/)) et le lancer (!) avec l'option "Disable Access Control", puis lancer l'un des scripts `docker\*Run.BAT` après avoir ajouté l'option '--debug' à la ligne de lancement du script.

Si vous voyez bien une fenêtre X s'afficher à l'écran c'est que l'environnement X11 est correctement configuré. Le mode débogue du script devrait fonctionner.

Si par contre rien ne s'affiche, il convient de chercher sur internet comment le faire fonctionner, il y a pleins de tutos pour cela. Ensuite vous pourrez utiliser le mode débogue.

## Première exécution :
Par default le script est muet (il n'affiche rien sur la console et ne lance pas la version graphique de Firefox). Il enregistre toutes les actions dans le fichier `INSTALL_DIR/veolia.log`.
Je vous recommande pour la première utilisation d'activer le mode débogue. Cela permet d'avoir une sortie visuelle de l'exécution du script sur la console et un suivi des actions dans Firefox.

Déroulement de l'exécution :

1. Chargement de tous les modules python --> si erreur installer les modules manquants (pip3 install ...)
2. Sanity check de l'environnement :
  * Version
  * Prérequis logiciel externe --> si erreur installer le logiciel manquant
  * Configuration Domoticz --> si erreur configurer correctement Domoticz
3. Connection au site Veolia et téléchargement de l'historique
4. Téléversement des données dans Domoticz

```shell
./veolia-idf-domoticz.py --run --debug
```
Afficher toutes les options disponibles :
```shell
./veolia-idf-domoticz.py --help
```

## Automatisation :
Une fois que la première exécution a terminé correctement, je vous recommande de planifier les exécutions une fois par jour.

Pour cela, ajoutez la ligne suivante à votre planificateur de tâches :
```shell
./veolia-idf-domoticz.py --run
```

Exemple ici avec `crontab` :

1. Démarrer l'édition de la table `crontab`.
```shell
crontab -e
```
2. Coller le contenu suivant :

```crontab
0 1 * * *       /opt/veolia-idf/veolia-idf-domoticz.py --run --log /var/log/veolia/veolia-idf.log
```

## Docker
Voir les fichiers `docker*Run.BAT`, `docker-compose.yml`, `DockerFile*`.

Ces scripts permettent aussi de valider le fonctionnement sous divers environnements Linux.  Il n'y a pas besoin de serveur X local tant que vous n'activez pas l'option débogue.

Vous avez bien évidemment besoin de [Docker](https://www.docker.com/).

### Démarrage rapide avec `docker compose`

Pour démarrer rapidement (après création du fichier de configuration `config.json`):

```shell
docker compose run --rm veolia-run
```

Ou en mode débogue (nécessite un serveur X local):
```shell
docker compose run --rm veolia-debug

```
### Scripts `docker*.BAT` (Windows)

La proposition `dockerAlpineRun.BAT` se mets en place le plus rapidement et c'est aussi le plus petit (<500Mo).

## Environnements testés:
* Debian Buster - chromium
* Debian Bullseye - chromium
* Alpine 3.16 - chromium
* Home Assistant/AppDaemon - Alpine Linux v3.14 - chromium
* Ubuntu 20.04 - firefox
* Ubuntu 21.04 - firefox (firefox-geckodriver non dispo sur Ubuntu 22.04).

A noter qu'Ubuntu supporte probablement aussi la solution avec chromium.

## Remerciements :
* [k20human](https://github.com/k20human)
* [guillaumezin](https://github.com/guillaumezin)
* [mdeweerd](https://github.com/mdeweerd) | support de Home Assistant + Docker
