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


def discover_jwst_products(instrument="NIRCAM*", calib_level=(2,3), n_obs=6,
                           min_mb=0.05, max_mb=None, proposal_id=None,
                           collection="JWST"):
    """Return sorted candidate list: [{obs_id, filename, size_mb, uri, proposal}].
    Public data only is guaranteed by MAST download service (proprietary files need auth).
    collection="Roman" will work as the future Roman adapter once public products exist;
    do NOT assume Roman formats/APIs are identical to JWST (mission rule)."""
    kw = dict(obs_collection=collection, dataproduct_type="image",
              instrument_name=instrument, calib_level=calib_level, intentType="science", dataRights="PUBLIC")
    if proposal_id:
        kw["proposal_id"] = proposal_id
    obs = Observations.query_criteria(**kw)
    if not len(obs):
        return []

    # Diverse public science fields, rotated hourly; never camp on the first
    # calibration star and its repeated exposures for days.
    import time
    if 't_min' in obs.colnames:obs.sort('t_min',reverse=True)
    indices=[];seen=set()
    for i,row in enumerate(obs):
        key=(str(row.get('target_name','')),str(row.get('filters','')))
        if key in seen:continue
        seen.add(key);indices.append(i)
        if len(indices)>=400:break
    start=(int(time.time()//3600)*n_obs)%len(indices)
    selected=[indices[(start+i)%len(indices)] for i in range(min(n_obs,len(indices)))]
    products = Observations.get_product_list(obs[selected])
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
    # Only displayable 2-D calibrated products (mission rule: defined behavior for
    # unsuitable data). _uncal = raw 4-D ramps, *ints = 3-D cubes -> skipped at discovery.
    good = ("_rate.fits", "_cal.fits", "_i2d.fits")
    out = [c for c in out if c["filename"].lower().endswith(good)]
    rank=lambda c: (0 if c['filename'].endswith('_i2d.fits') else 1 if c['filename'].endswith('_cal.fits') else 2,c['size_mb'])
    groups={}
    for c in out:groups.setdefault(c['obs_id'],[]).append(c)
    for group in groups.values():group.sort(key=rank)
    # Round-robin gives different fields a chance before repeated exposures.
    out=[]
    while groups:
        for key in list(groups):
            out.append(groups[key].pop(0))
            if not groups[key]:del groups[key]
    return out


def direct_urls(candidates):
    """Two anonymous download paths per product + official preview JPEG URL.
    MAST previews live next to the science file with a .jpg extension
    (verified live: Download/file?uri=mast:JWST/product/<stem>.jpg -> 200 image)."""
    urls = []
    for c in candidates:
        stem = c["filename"]
        if stem.lower().endswith(".fits"):
            stem = stem[:-5]
        urls.append({
            **c,
            "url_s3": f"https://s3.us-east-1.amazonaws.com/stpubdata/mast/JWST/product/{c['filename']}",
            "url_mast": f"https://mast.stsci.edu/api/v0.1/Download/file?uri={c['uri']}",
            "url_preview": f"https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:JWST/product/{stem}.jpg",
        })
    return urls


if __name__ == "__main__":
    import json
    cands = discover_jwst_products(min_mb=0.05, max_mb=400, n_obs=6)
    print(json.dumps(direct_urls(cands[:10]), indent=2))
