"""
Vue « mes vraies gardes » : la feuille de garde, corrigée par ce qui a été
réellement saisi dans Agatt.

Workflow métier :
  1. les chefs d'équipe montent la feuille de garde dans l'appli
  2. la feuille est validée, puis l'OPE la saisit dans Agatt et coche les cases
     (`Affectation.ope_checked`)
  3. à partir de là, les remplacements se font directement dans Agatt, plus
     dans l'appli

Conséquence : dès qu'une garde est intégralement cochée, Agatt fait foi pour
l'affichage. La feuille n'est jamais modifiée — c'est seulement la lecture qui
change.

Correspondance entre une affectation et le type d'occupation Agatt :

    garde JOUR  + piquet normal    → J12   (Garde 12h jour)
    garde NUIT  + piquet normal    → N12   (Garde 12h nuit)
    garde JOUR  + piquet astreinte → AJ    (Astreinte jour)
    garde NUIT  + piquet astreinte → AN    (Astreinte nuit)
"""
from collections import defaultdict
from datetime import date as DateType, timedelta
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Affectation, DispoAgatt, Garde, Personnel

# (slot, piquet est une astreinte) → type d'occupation Agatt
SLOT_TO_TYPE: dict[tuple[str, bool], str] = {
    ("JOUR", False): "J12",
    ("NUIT", False): "N12",
    ("JOUR", True): "AJ",
    ("NUIT", True): "AN",
}

# Horizon d'analyse : au-delà, la feuille n'est de toute façon pas saisie
HORIZON_JOURS = 92


def _normalize(s: str) -> str:
    """Supprime les accents et met en majuscules (même règle qu'à l'import)."""
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper().strip()


def _key(personne) -> tuple[str, str]:
    return (_normalize(personne.nom), _normalize(personne.prenom))


def _slot_name(garde: Garde) -> str:
    return garde.slot.name if hasattr(garde.slot, "name") else str(garde.slot)


def mes_gardes_reelles(
    db: Session,
    user: Personnel,
    start: DateType,
    limit: int = 20,
) -> list[dict]:
    """
    Retourne les gardes à venir de `user`, telles qu'elles sont réellement,
    triées par date puis créneau.

    Chaque élément porte :
      - `source` : "feuille" (saisie Agatt pas encore terminée) ou "agatt"
      - `etat`   : "ok"       → présent sur la feuille et dans Agatt
                   "remplace" → sur la feuille, absent d'Agatt (remplacé)
                   "ajout"    → absent de la feuille, présent dans Agatt
                                (on remplace quelqu'un)
      - `piquet` : None quand il n'est pas déductible (voir plus bas)
    """
    horizon = start + timedelta(days=HORIZON_JOURS)

    gardes: list[Garde] = (
        db.scalars(
            select(Garde)
            .options(joinedload(Garde.equipe))
            .where(Garde.date >= start, Garde.date <= horizon, Garde.validated == True)
            .order_by(Garde.date.asc(), Garde.slot.asc())
        )
        .unique()
        .all()
    )
    if not gardes:
        return []

    affectations: list[Affectation] = (
        db.scalars(
            select(Affectation)
            .options(joinedload(Affectation.piquet), joinedload(Affectation.personnel))
            .where(Affectation.garde_id.in_([g.id for g in gardes]))
        )
        .unique()
        .all()
    )
    affs_par_garde: dict[int, list[Affectation]] = defaultdict(list)
    for a in affectations:
        affs_par_garde[a.garde_id].append(a)

    # Occupations Agatt des dates concernées, indexées par (date, type)
    dispos: list[DispoAgatt] = db.scalars(
        select(DispoAgatt).where(
            DispoAgatt.date.in_({g.date for g in gardes}),
            DispoAgatt.type_occ.in_(set(SLOT_TO_TYPE.values())),
        )
    ).all()
    agatt: dict[tuple[DateType, str], set[tuple[str, str]]] = defaultdict(set)
    for d in dispos:
        agatt[(d.date, d.type_occ)].add((d.nom, d.prenom))

    ma_cle = _key(user)
    resultat: list[dict] = []

    for garde in gardes:
        affs = affs_par_garde.get(garde.id, [])
        if not affs:
            continue

        mon_aff = next((a for a in affs if a.personnel_id == user.id), None)
        slot = _slot_name(garde)

        # Tant que l'OPE n'a pas terminé sa saisie, la feuille reste la
        # référence : une garde en cours de saisie ne doit pas disparaître.
        saisie_terminee = all(bool(a.ope_checked) for a in affs)
        if not saisie_terminee:
            if mon_aff is not None:
                resultat.append(_item(garde, slot, mon_aff.piquet, "feuille", "ok"))
            continue

        # Agatt fait foi. Dans quel(s) type(s) d'occupation suis-je présent ?
        mes_types = [
            SLOT_TO_TYPE[(slot, astreinte)]
            for astreinte in (False, True)
            if (slot, astreinte) in SLOT_TO_TYPE
            and ma_cle in agatt[(garde.date, SLOT_TO_TYPE[(slot, astreinte)])]
        ]

        if not mes_types:
            # Absent d'Agatt : si j'étais sur la feuille, je me suis fait remplacer
            if mon_aff is not None:
                resultat.append(_item(garde, slot, mon_aff.piquet, "agatt", "remplace"))
            continue

        type_occ = mes_types[0]
        est_astreinte = type_occ in ("AJ", "AN")

        # Sur la feuille, au bon endroit → rien n'a bougé pour moi
        if mon_aff is not None and bool(mon_aff.piquet.is_astreinte) == est_astreinte:
            resultat.append(_item(garde, slot, mon_aff.piquet, "agatt", "ok"))
            continue

        # Je prends une place que je n'avais pas sur la feuille. Le piquet n'est
        # pas dans l'export : on ne le déduit que s'il n'y a aucune ambiguïté,
        # c'est-à-dire un seul départ et une seule arrivée sur ce type.
        resultat.append(
            _item(garde, slot, _piquet_devine(affs, agatt[(garde.date, type_occ)], est_astreinte),
                  "agatt", "ajout")
        )

    resultat.sort(key=lambda r: (r["date"], r["slot"]))
    return resultat[:limit]


def _piquet_devine(affs: list[Affectation], presents: set[tuple[str, str]], est_astreinte: bool):
    """
    Piquet libéré par la personne remplacée, si et seulement si le
    rapprochement est certain : un seul départ et une seule arrivée sur cette
    catégorie de piquet. Sinon None — mieux vaut ne rien afficher qu'un piquet
    faux.
    """
    de_la_categorie = [a for a in affs if bool(a.piquet.is_astreinte) == est_astreinte]
    sur_la_feuille = {_key(a.personnel) for a in de_la_categorie if a.personnel}

    partis = [a for a in de_la_categorie if a.personnel and _key(a.personnel) not in presents]
    arrivees = presents - sur_la_feuille

    if len(partis) == 1 and len(arrivees) == 1:
        return partis[0].piquet
    return None


def _item(garde: Garde, slot: str, piquet, source: str, etat: str) -> dict:
    return {
        "garde_id": garde.id,
        "date": garde.date,
        "slot": slot,
        "is_weekend": bool(garde.is_weekend),
        "is_holiday": bool(garde.is_holiday),
        "piquet": piquet,
        "equipe": getattr(garde, "equipe", None),
        "source": source,
        "etat": etat,
    }
