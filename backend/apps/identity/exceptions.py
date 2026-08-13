"""
Erreurs metier du contexte `identity`.

Elles heritent de la hierarchie gelee de `core` (§17) plutot que d en creer une
seconde : le contrat d erreur — `code`, `message`, `details`, `correlation_id`,
`trace_id` — reste unique pour tout le systeme, et le gestionnaire d exception
du Sprint 0 les traite sans modification.

`core` ne les connait pas et ne doit pas les connaitre (ADR-S-01) : la dependance
va bien de `identity` vers `core`, jamais l inverse.
"""

from __future__ import annotations

from apps.core.exceptions import AuthError, PermissionBusinessError, ValidationBusinessError


class EmailAlreadyExistsError(ValidationBusinessError):
    """
    400 — l adresse est deja utilisee.

    **400 et non 409, par respect d un contrat publie.** Semantiquement, 409
    decrirait mieux la situation : conflit avec une ressource existante. Mais le
    plan `plan-dev-v2/04-sprint-1-identite.md` §3.4 fige `EMAIL_ALREADY_EXISTS`
    en 400, et les clients React (S1-B) et Flutter (S1-C) seront ecrits contre
    ce contrat. Un code d erreur est une interface : le meilleur choix arrive
    trop tard une fois qu il est publie.

    **Divulgation assumee, pas oubliee.** Repondre franchement permet
    d enumerer les comptes. La seule parade complete — repondre 202 dans tous
    les cas et lever l ambiguite par courriel — suppose une chaine d envoi
    inexistante avant le contexte `notifying`. Repondre 202 aujourd hui
    jetterait silencieusement les inscriptions en doublon sans qu aucun
    utilisateur ne puisse comprendre pourquoi son compte n existe pas : moins
    sur en pratique, et franchement hostile.

    Le compromis retenu est donc de rendre l enumeration COUTEUSE plutot
    qu impossible : `throttle_scope = "register"`, 3 tentatives par heure et par
    adresse IP (§3.3 du plan). A rouvrir des que `notifying` existe.
    """

    default_code = "EMAIL_ALREADY_EXISTS"
    default_message = "Un compte existe deja pour cette adresse."


class UnderageError(ValidationBusinessError):
    """
    400 — l age minimum n est pas atteint (RM-13).

    Le SGBD porte deja la contrainte `ck_user_min_age_16`, mais une violation de
    contrainte remonterait en `IntegrityError` — donc en 500, avec un message
    inexploitable. Le service verifie donc AVANT, pour produire une erreur
    lisible ; la contrainte reste le filet qui tient face a une insertion directe.

    Les deux niveaux ne font pas double emploi : l un sert l utilisateur,
    l autre sert l integrite.
    """

    default_code = "UNDERAGE"
    default_message = "L inscription est reservee aux personnes de 16 ans et plus."


class TermsNotAcceptedError(ValidationBusinessError):
    """400 — les conditions generales n ont pas ete acceptees."""

    default_code = "TERMS_NOT_ACCEPTED"
    default_message = "L acceptation des conditions generales est obligatoire."


class InvalidFingerprintError(ValidationBusinessError):
    """
    400 — empreinte d appareil mal formee, ou plateforme inconnue.

    L empreinte est calculee cote client et reste opaque pour le serveur : il ne
    la recalcule jamais et n en deduit rien. Il valide uniquement le format —
    64 caracteres hexadecimaux MINUSCULES. On refuse plutot que de normaliser :
    mettre en minuscules a la volee masquerait un client qui envoie n importe
    quoi, et le probleme reapparaitrait ailleurs, sans lien apparent.
    """

    default_code = "INVALID_FINGERPRINT"
    default_message = "L empreinte d appareil est invalide."


class DeviceLockedError(PermissionBusinessError):
    """
    403 — un AUTRE appareil est deja lie a ce compte (RM-5).

    `details` porte un libelle TRONQUE de l appareil actif, sa date de liaison et
    la disponibilite du parcours de reinitialisation. Assez pour qu un
    utilisateur reconnaisse son ancien telephone — sinon le message est
    inutilisable — et assez peu pour ne pas renseigner quelqu un qui viendrait
    de prouver le mot de passe d autrui.

    **Cette erreur ne doit JAMAIS precederez la verification des identifiants.**
    Un mot de passe faux sur un compte verrouille renvoie 401
    `INVALID_CREDENTIALS`, jamais 403 : sinon l API confirme l existence du
    compte a qui n a rien prouve.
    """

    default_code = "DEVICE_LOCKED"
    default_message = "Un autre appareil est deja associe a ce compte."


class DeviceMismatchError(AuthError):
    """
    401 — jeton presente depuis un appareil qui n est pas celui lie.

    401 et non 403, deliberement : un jeton valide presente depuis un autre
    appareil est un jeton probablement vole. La bonne reponse est « cette
    identite n est pas prouvee », pas « vous n avez pas le droit ». Le lot
    S1-A.9 y branchera un journal de niveau AVERTISSEMENT.
    """

    default_code = "DEVICE_MISMATCH"
    default_message = "Ce jeton ne provient pas de l appareil associe au compte."


class InvalidCredentialsError(AuthError):
    """
    401 — adresse inconnue, mot de passe faux, ou compte desactive.

    **Un seul code pour les trois**, et c est le point le plus important de ce
    fichier. Distinguer « adresse inconnue » de « mot de passe faux » donnerait
    a un attaquant un oracle d existence : il enumererait les comptes sans
    jamais deviner un mot de passe.

    Un motif distinct pour « compte desactive » serait pire encore : il
    confirmerait a la fois que l adresse existe ET que le mot de passe a ete
    devine.

    Le corps identique ne suffit pas : le TEMPS de reponse doit l etre aussi.
    Voir `AuthenticationService._verify_credentials` et son hachage factice.
    """

    default_code = "INVALID_CREDENTIALS"
    default_message = "Adresse ou mot de passe incorrect."
