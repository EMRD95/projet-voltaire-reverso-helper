@echo off
rem Copie ce fichier vers koboldcpp_config.cmd si besoin.
rem Le seul truc a changer c'est le port si koboldcpp tourne ailleurs qu'en 5001.

set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001
rem 0 = n'ajoute pas instructions.txt au prompt koboldcpp (defaut), 1 = l'utiliser
set VOLTAIRE_KOBOLDCPP_USE_INSTRUCTIONS=0
