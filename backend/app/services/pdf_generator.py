from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── Palette — thème light planning ─────────────────────────
# Fond page / surface
_WHITE       = colors.HexColor("#ffffff")
_SURFACE_2   = colors.HexColor("#f8f6ff")
_SURFACE_3   = colors.HexColor("#f0eeff")
# Texte
_TEXT        = colors.HexColor("#1a1530")
_TEXT_MUTED  = colors.HexColor("#6b6488")
# Grille
_BORDER      = colors.HexColor("#d5cfee")
# En-tête garde
_JOUR_HDR    = colors.HexColor("#6d28d9")   # violet foncé (--header-day light)
_NUIT_HDR    = colors.HexColor("#1e1b40")   # bleu nuit
_HDR_FG      = colors.white
# Fond des lignes garde
_DAY_ROW_BG  = colors.HexColor("#fffbeb")   # --card-day-bg light (jaune chaud)
_NIGHT_ROW_BG= colors.HexColor("#f5f3ff")   # --card-night-bg light (violet pâle)
# Colonne label (piquets)
_LABEL_BG    = colors.HexColor("#ebe7ff")   # --raised light
# Statuts
_NON_AFF_C   = colors.HexColor("#d97706")   # --warn light
_NON_AFF_BG  = colors.HexColor("#fffbeb")
_INDISPO_C   = colors.HexColor("#dc2626")   # --danger light
_INDISPO_BG  = colors.HexColor("#fef2f2")

_JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 12 * mm


def _par(text: str, *, color=_TEXT, size: float = 7.0,
         bold: bool = False, align: str = "CENTER") -> Paragraph:
    style = ParagraphStyle(
        "fg_cell",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        textColor=color,
        leading=size * 1.35,
        alignment=TA_CENTER if align == "CENTER" else TA_LEFT,
        wordWrap="CJK",
    )
    return Paragraph(text.replace("\n", "<br/>"), style)


def generate_feuille_garde_pdf(
    equipe_label: str,
    mois_label: str,
    gardes: list[dict],
    # [{"id": int, "date": date, "slot": "JOUR"|"NUIT"}]  triés date+slot
    piquets: list[dict],
    # [{"id": int, "label": str}]  — TOUS les piquets, même vides
    aff_map: dict[int, dict[int, str]],
    # {garde_id: {piquet_id: agent_fullname}}
    non_aff_map: dict[int, list[str]],
    # {garde_id: [fullname, ...]}
    indispo_map: dict[int, list[str]],
    # {garde_id: [fullname, ...]}
) -> bytes:
    """
    PDF paysage A4 — thème light planning :
    - 1 colonne par garde (en-tête : date + slot)
    - 1 ligne par piquet (tous affichés, même vides)
    - Ligne « Non affectés »
    - Ligne « Indisponibles »
    """
    buf = BytesIO()
    n_gardes  = len(gardes)
    n_piquets = len(piquets)

    # ── Largeurs colonnes ───────────────────────────────────
    usable_w = PAGE_W - 2 * MARGIN
    label_w  = min(40 * mm, usable_w * 0.14)
    col_w    = (usable_w - label_w) / max(n_gardes, 1)
    col_widths = [label_w] + [col_w] * n_gardes

    # Taille police adaptée
    fs = max(5.0, min(8.0, 8.0 * 14 / max(n_gardes, 14)))

    # ── En-tête : une colonne par garde ────────────────────
    header_row = [_par("", size=fs)]
    for g in gardes:
        d    = g["date"]
        slot = g["slot"]
        day  = _JOURS_FR[d.weekday()]
        txt  = f"<b>{day} {d.strftime('%d/%m')}</b><br/>{slot}"
        header_row.append(_par(txt, color=_HDR_FG, size=fs))

    # ── Lignes piquets (tous, même vides) ──────────────────
    piquet_rows = []
    for pq in piquets:
        row = [_par(pq["label"], color=_TEXT, size=fs, bold=True, align="LEFT")]
        for g in gardes:
            agent = (aff_map.get(g["id"]) or {}).get(pq["id"], "")
            row.append(_par(agent, color=_TEXT, size=fs))
        piquet_rows.append(row)

    # ── Ligne non affectés ──────────────────────────────────
    non_aff_row = [_par("Non affectés", color=_NON_AFF_C, size=fs, bold=True, align="LEFT")]
    for g in gardes:
        txt = ", ".join(non_aff_map.get(g["id"], []))
        non_aff_row.append(_par(txt, color=_NON_AFF_C, size=fs, align="LEFT"))

    # ── Ligne indisponibles ─────────────────────────────────
    indispo_row = [_par("Indisponibles", color=_INDISPO_C, size=fs, bold=True, align="LEFT")]
    for g in gardes:
        txt = ", ".join(indispo_map.get(g["id"], []))
        indispo_row.append(_par(txt, color=_INDISPO_C, size=fs, align="LEFT"))

    table_data = [header_row] + piquet_rows + [non_aff_row, indispo_row]

    # ── Styles table ────────────────────────────────────────
    idx_non_aff = 1 + n_piquets
    idx_indispo = 2 + n_piquets

    style = [
        # Padding global
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        # Grille fine
        ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
        # Colonne label — fond lavande
        ("BACKGROUND",    (0, 0), (0, -1), _LABEL_BG),
        # Ligne d'en-tête label : même lavande
        ("BACKGROUND",    (0, 0), (0, 0), _SURFACE_3),
        # Séparateurs épais avant non-affectés et indisponibles
        ("LINEABOVE",     (0, idx_non_aff), (-1, idx_non_aff), 1.2, _BORDER),
        ("LINEABOVE",     (0, idx_indispo), (-1, idx_indispo), 1.2, _BORDER),
        # Fond lignes statuts
        ("BACKGROUND",    (0, idx_non_aff), (-1, idx_non_aff), _NON_AFF_BG),
        ("BACKGROUND",    (0, idx_indispo), (-1, idx_indispo), _INDISPO_BG),
    ]

    # En-têtes de garde colorés selon JOUR/NUIT
    for col_i, g in enumerate(gardes, start=1):
        bg = _JOUR_HDR if g["slot"] == "JOUR" else _NUIT_HDR
        style.append(("BACKGROUND", (col_i, 0), (col_i, 0), bg))

    # Fond des lignes piquets selon JOUR/NUIT de chaque colonne
    # + alternance blanc / très léger pour les lignes
    for row_i in range(1, 1 + n_piquets):
        row_bg = _WHITE if row_i % 2 == 0 else _SURFACE_2
        style.append(("BACKGROUND", (1, row_i), (-1, row_i), row_bg))
        # Colonne label reste lavande (déjà défini globalement)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(style))

    # ── Titre ───────────────────────────────────────────────
    title_style = ParagraphStyle(
        "fg_title",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=_TEXT,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "fg_sub",
        fontName="Helvetica",
        fontSize=9,
        textColor=_TEXT_MUTED,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    title    = Paragraph(
        f"Feuille de garde de l'équipe {equipe_label}",
        title_style,
    )
    subtitle = Paragraph(mois_label, subtitle_style)

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )
    doc.build([title, subtitle, Spacer(1, 3 * mm), table])
    return buf.getvalue()
