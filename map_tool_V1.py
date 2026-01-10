import streamlit as st
import pandas as pd
import requests
from typing import Dict, Any

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
        return f"{z.get('Zone')} – {z.get('Land Use')}"
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

    return "; ".join(sorted(labels))


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


# ------------------------------------------------------------------
# Main pipeline → DataFrame row
# ------------------------------------------------------------------
def build_site_dataframe(lotid: str) -> pd.DataFrame:
    lot_info = get_lot_info(lotid)

    cad_id = lot_info["cadId"]
    prop_id = get_property_id(cad_id)

    overlays = get_overlays(cad_id, layers="epi")
    overlay_idx = index_overlays_by_layer(overlays)

    address = get_address(prop_id)
    council = get_council(prop_id)

    row = {
        "Address": address,
        "Site Area (ha)": "",
        "Lot Identifier": lotid,
        "Council": council[0],
        "Regional Plan Boundary": parse_regional_plan(overlay_idx),
        "Local Aboriginal Land Council": parse_lalc(overlay_idx),
        "Land Zoning": parse_land_zoning(overlay_idx),
        "BPA": "",
        "Special Provisions": "; ".join(
            sorted(
                filter(
                    None,
                    [
                        parse_special_provisions(overlay_idx),
                        parse_height(overlay_idx),
                        parse_acid_sulfate_soil(overlay_idx),
                    ],
                )
            )
        ),
    }


    return pd.DataFrame([row])


# ------------------------------------------------------------------
# Example usage
# ------------------------------------------------------------------
if __name__ == "__main__":
    lotid = "37/G/DP8324"

    df = build_site_dataframe(lotid)

    print(df)



st.set_page_config(
    page_title="NSW Planning Lot Lookup",
    layout="wide"
)

st.title("🏗️ NSW Planning Portal – Lot Lookup")

st.markdown(
    """
    Enter a **Lot Identifier** (e.g. `37/G/DP8324`) to retrieve
    planning controls and overlays from the NSW Planning Portal API.
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
        placeholder="37/G/DP8324"
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
