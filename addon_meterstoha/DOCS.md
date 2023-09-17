# MetersToHA Home Assistant Add-on

MetersToHA est plus simple à mettre en place avec ce module complémentaire

## Configuration

Pour plus d'information voir
[https://github.com/mdeweerd/MetersToHA](https://github.com/mdeweerd/MetersToHA).

Des options sont nécessaires, cela dépend de votre situation lesquelles.
Par exemple, les options "GRDF" sont inutiles si vous cherchez seulement à
obtenir les informations de véolia.

|                      |                                                                                                                                                                                                                                                                                                                   |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| captchaservice       | Le service de résolution de captcha                                                                                                                                                                                                                                                                               |
| token_captchaservice | La clef API (Token) nécessaire pour le service de résolution de captcha.                                                                                                                                                                                                                                          |
| grdf_event           | Nom de l'événement Home Assistant qui permet de déclencher MetersToHA pour GRDF                                                                                                                                                                                                                                   |
| grdf_login           | Identification pour le site GRDF (adresse mél.)                                                                                                                                                                                                                                                                   |
| grdf_password        | Mot de passe pour le site GRDF                                                                                                                                                                                                                                                                                    |
| grdf_pce             | GRDF Numéro du Point de Comptage et d'Estimation (PCE)                                                                                                                                                                                                                                                            |
| ha_server            | Serveur Home Assistant vers lequel envoyer les données                                                                                                                                                                                                                                                            |
| ha_token             | Long Lived Token created on your Home Assistant Server for MetersToHA                                                                                                                                                                                                                                             |
| timeout              | Un délai en secondes utilisé comme délai d'expiration pour diverses de Meters2HA                                                                                                                                                                                                                                  |
| type                 | Le type de votre serveur ('ha'=Home Assistant, mqtt, ...)                                                                                                                                                                                                                                                         |
| veolia_event         | Nom de l'événement Home Assistant qui permet de déclencher MetersToHA pour Veolia                                                                                                                                                                                                                                 |
| veolia_contract      | N° de contrat Veolia                                                                                                                                                                                                                                                                                              |
| veolia_login         | Identifiant (email) pour le site Veolia (email)                                                                                                                                                                                                                                                                   |
| veolia_password      | Mot de passe pour le site Veolia                                                                                                                                                                                                                                                                                  |
| skip_download        | Ne télécharge pas les données, mais utilisera les données déjà présentes localement.  Utile lors de la mise au point de la configuration, pendant le débogue, ou lorsque vous téléchargez le fichier par d'autre moyens (car les données sont quand même interprétées et envoyées vers votre système Domotique).  |
| log_level            | Impacte les messages remonté.  Le niveau "trace" entraine la présence de chaque ligne exécutée dans 'service.log'                                                                                                                                                                                                 |
| debug                | Ouvrira le navigateur sur le terminal X spécifié dans DISPLAY                                                                                                                                                                                                                                                     |
| DISPLAY              | Spécification complète de l'adresse du terminal X accessible depuis votre instance Home Assistance.  Par exemple, vous lancez MobiXterm sur votre PC qui a comme IP 10.33.2.69, et les connexions depuis votre réseau privé vers ce serveur sont autorisés.  La valeur "10.33.2.69:0.0" est en principe la bonne. |
| insecure             | Accepte les certificats autosignés.  Utile seulement lorsque ce n'est pas le serveur Home Assistant du module complémentaire ("add-on") est utilisé.                                                                                                                                                              |
| local_config         | Lorsque actif, maintient les données de configuration de chrome entre les lancements.                                                                                                                                                                                                                             |
| screenshot           | Prend des captures d'écran qui peuvent être utiles au débogue.                                                                                                                                                                                                                                                    |
| keep_output          | Si active, la suppression des fichiers intermédiaires et de données n'est pas effectuée.                                                                                                                                                                                                                          |
| mqtt_login           | Identifiant pour Serveur mqtt                                                                                                                                                                                                                                                                                     |
| mqtt_password        | Mot de passe pour Serveur mqtt                                                                                                                                                                                                                                                                                    |
| mqtt_server          | Mot de passe pour Serveur mqtt                                                                                                                                                                                                                                                                                    |
| mqtt_port            |                                                                                                                                                                                                                                                                                                                   |
| domoticz_login       | Identifiant du serveur Domoticz                                                                                                                                                                                                                                                                                   |
| domoticz_password    | Mot de passe du serveur Domoticz                                                                                                                                                                                                                                                                                  |
| domoticz_server      | Nom/IP du serveur Domoticz                                                                                                                                                                                                                                                                                        |
| domoticz_idx         | Index pour l'enregistrement sous Domoticz                                                                                                                                                                                                                                                                         |
| git_version          | La version GIT à récupérer lors du (re)démarrage du module.  Rien: la branche 'main'.  Vous pouvez mettre 'dev' pour la branche de développement, un hash d'un commit git, un tag.                                                                                                                                |

## Version

Pour le moment, le fonctionnment du module complémentaire est atypique: à
chaque démarrage du module celui-ci va chercher la dernière version du
programme de la branche 'main'.

Ceci permet de changer de version plus rapidement (utile pendant la mise au
point du module). A terme, la version devrait être figé dans l'image de
l'addon mais si le paramètre est défini, il aura le même effet
qu'actuellement.

## Changelog & Releases

Voir l'historique "Git" sur
[https://github.com/mdeweerd/MetersToHA](https://github.com/mdeweerd/MetersToHA)
pour le moment.

## Débogue

Avec un `log_level` défini à `debug` vous aurez la plupart des informations
nécessaires.

Vous les rendez accessibles en les mettant dans un sous-répertoire de
`/config` par exemple.

```yaml
logs_folder: /config/MetersToHA
download_folder: /config/csv
```

Le journal du module complémentaire donne également des informations
utiles.

## Support

Faire une demande sur
[https://github.com/mdeweerd/MetersToHA/issues](https://github.com/mdeweerd/MetersToHA/issues)
ou le forum
[Home Assistatn Communauté Francophone](https://forum.hacf.fr/).

## Contribuer

Vous pouvez contribuer de diverses manières:

- Mettre à jour la documentation;
- Mettre au point la création des images de distrubution;
- Mettre au point le processus de "release";
- Ajouter d'autres fournisseurs à MetersToHA;
- Aider les nouveaux utilisateurs sur les forums, y partager votre
  expérience.

## License

MIT pour le module complémentaire, GPL pour le script meters2ha.py.
