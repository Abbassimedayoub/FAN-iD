"""
Champ email insensible à la casse, adossé au type PostgreSQL `citext`.

**Pourquoi un champ personnalisé** : Django fournissait `CIEmailField` dans
`django.contrib.postgres.fields`, déprécié en 4.2 et **supprimé en 5.1**. Le
projet tourne sous Django 5.2 : il n'existe plus aucun champ CITEXT natif.

**Pourquoi `citext` plutôt qu'un index fonctionnel** `UniqueConstraint(Lower("email"))` :
le plan S1 §2.5 exclut explicitement l'index fonctionnel. `citext` rend en outre
la comparaison insensible à la casse *partout* — `WHERE email = ...`, jointures,
`get()` — sans que chaque appelant ait à penser à `LOWER()`. Un seul oubli
suffirait à réintroduire la faille d'unicité que la contrainte est censée fermer.

Vérifié sur PostgreSQL 16 (ADR-S1-01) : insérer `Fan@Example.TEST` puis
`fan@example.test` viole l'index unique, et `WHERE email = 'FAN@EXAMPLE.TEST'`
retrouve la ligne sans `LOWER()`.
"""

from django.db import models


class CITextEmailField(models.EmailField):
    """`EmailField` stocké en `citext` sur PostgreSQL.

    Sur tout autre backend, le champ retombe sur le type d'origine : les
    validations Django (format RFC 5322, longueur) restent identiques, seule
    l'insensibilité à la casse au niveau du SGBD est perdue. Le projet ne cible
    que PostgreSQL ; ce repli existe pour ne pas rendre le modèle inchargeable
    sous SQLite lors d'une inspection hors contexte.
    """

    def db_type(self, connection) -> str | None:
        if connection.vendor == "postgresql":
            return "citext"
        return super().db_type(connection)
