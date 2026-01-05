"""
AWS Lambda handler pour Agent Lynkia.

Ce fichier sert de point d'entrée pour le déploiement AWS Lambda.
Mangum adapte l'application FastAPI pour fonctionner avec Lambda.
"""

from mangum import Mangum
from main import app

# Handler Lambda
# lifespan="off" car Lambda ne supporte pas les événements de cycle de vie
handler = Mangum(app, lifespan="off")
