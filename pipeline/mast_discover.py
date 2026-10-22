"""
mast_discover.py - Discovery of public JWST products on MAST via astroquery (anonymous access works
for public data). Size-aware selection keeps the daily download inside a byte budget.
"""
from __future__ import annotations

from astroquery.mast import Observations


def _to_mb(size_field):
    try:
        return float(size_field) / (1024.0 * 1024.0)
    except (TypeError, ValueError):
        return -1.0


def discover_jwst_products(instrument="NIRCAM*", calib_level=2, n_obs=6,
                           min_mb=0.05, max_mb=None, proposal_id=None,
                           collection="JWST"):
    """Return sorted candidate list: [{obs_id, filename, size_mb, uri, proposal}].
    Public data only is guaranteed by MAST download service (proprietary files need auth).
    collection="Roman" will work as the future Roman adapter once public products exist;
    do NOT assume Roman formats/APIs are identical to JWST (mission rule)."""
    kw = dict(obs_collection=collection, dataproduct_type="image",
              instrument_name=instrument, calib_level=calib_level)
    if proposal_id:
        kw["proposal_id"] = proposal_id
    obs = Observations.query_criteria(**kw)
    if not len(obs):
        return []

    products = Observations.get_product_list(obs[:n_obs])
    sci = Observations.filter_products(products, productType="SCIENCE", extension="fits")
    out = []
    for row in sci:
        size_mb = _to_mb(row.get("size"))
        if size_mb < min_mb or (max_mb is not None and size_mb > max_mb):
            continue
        fn = str(row.get("productFilename"))
        out.append({
            "obs_id": str(row.get("obs_id", "")),
            "filename": fn,
            "size_mb": round(size_mb, 3),
            "uri": f"mast:JWST/product/{fn}",
            "proposal": str(row.get("proposal_id", "")),
        })
    out.sort(key=lambda x: x["size_mb"])
    return out


def direct_urls(candidates):
    """Two anonymous download paths per product (fallback order)."""
    urls = []
    for c in candidates:
        urls.append({
            **c,
            "url_s3": f"https://s3.us-east-1.amazonaws.com/stpubdata/mast/JWST/product/{c['filename']}",
            "url_mast": f"https://mast.stsci.edu/api/v0.1/Download/file?uri={c['uri']}",
        })
    return urls


if __name__ == "__main__":
    import json
    cands = discover_jwst_products(min_mb=0.05, max_mb=400, n_obs=6)
    print(json.dumps(direct_urls(cands[:10]), indent=2))
