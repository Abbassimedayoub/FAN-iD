"""
Fixtures partagées par tous les bounded contexts.

**Pourquoi ce fichier existe** : les 4 rôles sont créés par une migration de
données (`identity/0003_seed_roles`). Or un test marqué
`@pytest.mark.django_db(transaction=True)` suit la sémantique
`TransactionTestCase` de Django : à la fin du test, **toutes les tables sont
vidées** — y compris les lignes insérées par les migrations. Django propose
`serialized_rollback=True` pour les restaurer, au prix d'une sérialisation
complète de la base avant chaque test, ce qui coûte plusieurs secondes par test.

La fixture ci-dessous rétablit le référentiel de façon idempotente et
instantanée. Elle rend surtout la suite **déterministe** : sans elle, le
résultat dépend de l'ordre dans lequel les tests transactionnels tombent dans
les workers `pytest -n auto`, et le symptôme se déplace d'une exécution à
l'autre — exactement ce qui s'est produit lors de l'intégration de ce lot.

Ce fichier vit dans `apps/` et non dans `apps/core/tests/` : il peut donc
importer `apps.identity` sans contrevenir au contrat import-linter
`core-is-independent`, qui couvre `apps.core` et tous ses sous-modules.
"""

import pytest


@pytest.fixture
def roles(db):
    """Garantit la présence des 4 rôles, avec leurs identifiants stables."""
    from apps.identity.constants import ROLE_IDS
    from apps.identity.models import Role

    for name, role_id in ROLE_IDS.items():
        Role.objects.get_or_create(id=role_id, defaults={"name": name})
    return {role.name: role for role in Role.objects.all()}
