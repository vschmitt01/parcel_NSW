import streamlit as st
import requests
import pandas as pd
import numpy as np
from typing import Dict, Any
# from shapely.geometry import Polygon

BASE_URL = "https://api.apps1.nsw.gov.au/planning/viewersf/V1/ePlanningApi"

HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.planningportal.nsw.gov.au",
    "Referer": "https://www.planningportal.nsw.gov.au/",
    "User-Agent": "Mozilla/5.0"
}


# ------------------------------------------------------------------
# Core API helpers
# ------------------------------------------------------------------
def api_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        headers=HEADERS,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def get_lot_info(lotid: str) -> Dict[str, Any]:
    return api_get("lot", {"l": lotid, "noOfRecords": 1})[0]


def get_boundary(cad_id: str) -> Dict[str, Any]:
    return api_get("boundary", {"id": cad_id, "Type": "lot"})


def get_overlays(cad_id: str, layers: str = "epi") -> Dict[str, Any]:
    return api_get("layerintersect", {
        "type": "lot",
        "id": cad_id,
        "layers": layers
    })


def get_address(prop_id: str) -> Dict[str, Any]:
    return api_get("address", {"id": prop_id, "Type": "property"})


def get_property_id(cad_id: str) -> str | None:
    return api_get("property", {"cadId": cad_id})

def get_council(prop_id: str) -> Dict[str, Any]:
    return api_get("council", {"propId": prop_id})


# ------------------------------------------------------------------
# Overlay Parsing
# ------------------------------------------------------------------
def index_overlays_by_layer(overlays: list[dict]) -> dict[str, list[dict]]:
    """
    Returns: { layerName: results }
    """
    return {
        layer["layerName"]: layer.get("results", [])
        for layer in overlays
    }


def parse_land_zoning(overlay_idx: dict) -> str | None:
    zoning = overlay_idx.get("Land Zoning Map")
    if zoning:
        z = zoning[0]
        return f"{z.get('Zone')}"
    return None


def parse_regional_plan(overlay_idx: dict) -> str | None:
    rp = overlay_idx.get("Regional Plan Boundary")
    if rp:
        return rp[0].get("title")
    return None


def parse_lalc(overlay_idx: dict) -> str | None:
    lalc = overlay_idx.get("Local Aboriginal Land Council")
    if lalc:
        return lalc[0].get("Local Council Name")
    return None


def parse_special_provisions(overlay_idx: dict) -> str | None:
    sp = overlay_idx.get("Special Provisions")
    if not sp:
        return None

    labels = set()
    for r in sp:
        if r.get("Type"):
            labels.add(r["Type"])

    return " / ".join(sorted(labels))


def parse_height(overlay_idx: dict) -> str | None:
    rows = overlay_idx.get("Height of Buildings Map")
    if not rows:
        return None

    entries = set()

    for r in rows:
        height = r.get("Maximum Building Height") or r.get("title")
        units = r.get("Units", "m")
        clause = r.get("Legislative Clause")
        epi = r.get("EPI Name")

        parts = []

        if height:
            parts.append(f"{height} {units}".strip())

        meta = ", ".join(p for p in [clause, epi] if p)
        if meta:
            parts.append(f"({meta})")

        if parts:
            entries.add(" ".join(parts))

    if not entries:
        return None

    return "Height of Buildings: " + "; ".join(sorted(entries))



def parse_acid_sulfate_soil(overlay_idx: dict) -> str | None:
    rows = overlay_idx.get("Acid Sulfate Soils Map")
    if not rows:
        return None

    entries = set()

    for r in rows:
        ass_class = r.get("Class") or r.get("title")
        clause = r.get("Legislative Clause")
        epi = r.get("EPI Name")

        parts = []

        if ass_class:
            parts.append(ass_class)

        meta = ", ".join(p for p in [clause, epi] if p)
        if meta:
            parts.append(f"({meta})")

        if parts:
            entries.add(" ".join(parts))

    if not entries:
        return None

    return "Acid Sulfate Soils: " + "; ".join(sorted(entries))


def parse_bushfire_prone_land(overlay_idx: dict) -> str | None:
    rows = overlay_idx.get("Bushfire Prone Land (Non-EPI)")
    if not rows:
        return None

    entries = set()

    for r in rows:
        category = r.get("Category") or r.get("title")
        parts = []

        if category:
            parts.append(category)

        if parts:
            entries.add(" ".join(parts))

    if not entries:
        return None

    return "/ ".join(sorted(entries))


def parse_groundwater_vulnerability(overlay_idx: dict) -> str | None:
    rows = overlay_idx.get("Natural Resource - Groundwater Vulnerability Map")
    if not rows:
        return None

    entries = set()

    for r in rows:
        gw_class = r.get("Class") or r.get("title")
        epi = r.get("EPI Name")
        commenced = r.get("Commenced Date")

        parts = []

        if gw_class:
            parts.append(gw_class)

        meta = ", ".join(
            p for p in [
                epi,
                f"Commenced {commenced}" if commenced else None,
            ]
            if p
        )

        if meta:
            parts.append(f"({meta})")

        if parts:
            entries.add(" ".join(parts))

    if not entries:
        return None

    return "Groundwater Vulnerability: " + "; ".join(sorted(entries))


def parse_terrestrial_biodiversity(overlay_idx: dict) -> str | None:
    rows = overlay_idx.get("Terrestrial Biodiversity Map")
    if not rows:
        return None

    entries = set()

    for r in rows:
        bio_class = r.get("Class") or r.get("title")
        epi = r.get("EPI Name")
        commenced = r.get("Commenced Date")

        parts = []

        if bio_class:
            parts.append(bio_class)

        meta = ", ".join(
            p for p in [
                epi,
                f"Commenced {commenced}" if commenced else None,
            ]
            if p
        )

        if meta:
            parts.append(f"({meta})")

        if parts:
            entries.add(" ".join(parts))

    if not entries:
        return None

    return "Terrestrial Biodiversity: " + "; ".join(sorted(entries))


def parse_heritage_flag(overlay_idx: dict) -> str:
    """
    Returns 'Y' if Heritage Map overlay exists, else 'N'
    """
    rows = overlay_idx.get("Heritage Map")
    return "Y" if rows else "N"


def parse_crown_land_flag(overlay_idx: dict) -> str:
    """
    Returns 'Y' if Crown Land overlay exists, else 'N'
    """
    rows = overlay_idx.get("Crown Land")
    return "Y" if rows else "N"


# def compute_area_ha(geometry: dict) -> float:
#     rings = geometry.get("rings")
#     if not rings or not rings[0]:
#         return 0.0

#     # Only use the first ring (outer boundary)
#     poly = Polygon(rings[0])
#     area_m2 = poly.area  # area in m²
#     area_ha = np.round(area_m2 / 10000, 2)  # convert to hectares
#     return area_ha


# ------------------------------------------------------------------
# Main pipeline → DataFrame row
# ------------------------------------------------------------------
def build_site_dataframe(lotid: str) -> pd.DataFrame:
    lot_info = get_lot_info(lotid)

    cad_id = lot_info["cadId"]
    prop_id = get_property_id(cad_id)
    boundaries = get_boundary(cad_id)[0]['geometry']
    

    overlays = get_overlays(cad_id, layers="epi")
    overlay_idx = index_overlays_by_layer(overlays)

    address = get_address(prop_id)
    council = get_council(prop_id)

    row = {
        "Address": address,
        "Site Area (ha)": "", #compute_area_ha(boundaries),
        "Lot Identifier": lotid,
        "Council": council[0],
        "Regional Plan Boundary": parse_regional_plan(overlay_idx),
        "Local Aboriginal Land Council": parse_lalc(overlay_idx),
        "Land Zoning": parse_land_zoning(overlay_idx),
        "BPA": parse_bushfire_prone_land(overlay_idx),
        "Special Provisions": "/ ".join(
            sorted(
                filter(
                    None,
                    [
                        parse_special_provisions(overlay_idx),
                        parse_height(overlay_idx),
                        parse_acid_sulfate_soil(overlay_idx),
                        parse_groundwater_vulnerability(overlay_idx),
                        parse_terrestrial_biodiversity(overlay_idx),
                    ],
                )
            )
        ),
        "Crown Land": parse_crown_land_flag(overlay_idx),
        "Heritage": parse_heritage_flag(overlay_idx),
    }


    return pd.DataFrame([row])



st.set_page_config(
    page_title="NSW Planning Helper",
    layout="wide"
)

st.title("NSW Planning Helper")

st.markdown(
    """
    Enter a **Lot Identifier** (`-/-/-`) to retrieve
    planning controls and overlays from the NSW Planning Portal.
    """
)

# ------------------------------------------------------------------
# Session state: persistent table
# ------------------------------------------------------------------
if "sites_df" not in st.session_state:
    st.session_state.sites_df = pd.DataFrame(
        columns=[
            "Address",
            "Site Area (ha)",
            "Lot Identifier",
            "Council",
            "Regional Plan Boundary",
            "Local Aboriginal Land Council",
            "Land Zoning",
            "BPA",
            "Special Provisions",
        ]
    )

# ------------------------------------------------------------------
# Input form
# ------------------------------------------------------------------
with st.form("lot_form", clear_on_submit=True):
    lotid = st.text_input(
        "Lot Identifier",
        placeholder="-/-/-"
    )

    submitted = st.form_submit_button("Add Lot")

# ------------------------------------------------------------------
# Handle submission
# ------------------------------------------------------------------
if submitted:
    if not lotid.strip():
        st.warning("Please enter a Lot Identifier.")
    else:
        with st.spinner("Fetching planning data..."):
            try:
                new_row = build_site_dataframe(lotid)

                # Avoid duplicates
                if lotid in st.session_state.sites_df["Lot Identifier"].values:
                    st.info(f"Lot `{lotid}` is already in the table.")
                else:
                    st.session_state.sites_df = pd.concat(
                        [st.session_state.sites_df, new_row],
                        ignore_index=True
                    )

                st.success(f"Lot `{lotid}` added successfully.")

            except Exception as e:
                st.error(f"Failed to fetch data for `{lotid}`")
                st.exception(e)

# ------------------------------------------------------------------
# Display table
# ------------------------------------------------------------------
st.subheader("📋 Site Summary")

st.dataframe(
    st.session_state.sites_df,
    use_container_width=True,
    hide_index=True
)

# ------------------------------------------------------------------
# Optional: export
# ------------------------------------------------------------------
if not st.session_state.sites_df.empty:
    csv = st.session_state.sites_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        csv,
        "nsw_planning_sites.csv",
        "text/csv",
    )

