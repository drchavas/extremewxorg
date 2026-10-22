#!/usr/bin/env python3
"""ghcnh_daily.py CACHE DAILY [--keep] -- reduce GHCNh station-year parquet files to
one small daily table per station: daily/<ID>.npz with
   day  int32   days since 1970-01-01 (UTC date, as ISD/GHCNh DATE)
   fz   uint8   distinct UTC hours with a report whose text contains FZRA (not FZRANO)
   pk   uint8   highest 'PK WND' gust in the day, kt (0 = none; >99 kt dropped as garbled)
Every UTC day with at least one report (REM or temperature present) gets a row, so
row count = observed days (the completeness screen). Each parquet is deleted after it
is reduced unless --keep. Re-running merges new years into existing tables."""
import glob, os, re, sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
FZRA = re.compile(r"FZRA(?!NO)")
PKWND = re.compile(r"PK WND \d{3}(\d{2,3})/(?:\d{4}|\d{2})(?!\d)")
EPOCH = pd.Timestamp("1970-01-01")


def reduce_file(f):
    t = pq.read_table(f, columns=["DATE", "REM", "temperature"]).to_pandas()
    t = t[t.REM.notna() | t.temperature.notna()]
    if t.empty:
        return None
    dt = pd.to_datetime(t.DATE, errors="coerce"); ok = dt.notna()
    t, dt = t[ok], dt[ok]
    day = ((dt.dt.normalize() - EPOCH).dt.days).astype(np.int32)
    rem = t.REM.fillna("").astype(str)
    fz = rem.str.contains(FZRA)
    fzh = pd.Series(dt.dt.hour.values, index=day.values)[fz.values]
    fzc = fzh.groupby(level=0).nunique() if len(fzh) else pd.Series(dtype=int)
    g = rem.str.extract(PKWND)[0].astype(float)
    g = g.where(g <= 99)
    pk = pd.Series(g.values, index=day.values).groupby(level=0).max()
    days = np.unique(day.values)
    return pd.DataFrame({"day": days,
                         "fz": fzc.reindex(days).fillna(0).astype(np.uint8).values,
                         "pk": pk.reindex(days).fillna(0).astype(np.uint8).values})


def main(cache, out, keep=False):
    os.makedirs(out, exist_ok=True)
    by = {}
    for f in sorted(glob.glob(os.path.join(cache, "*", "USW*.parquet"))):
        by.setdefault(os.path.basename(f)[:-8], []).append(f)
    import multiprocessing as mp
    with mp.Pool(int(os.environ.get("NPROC", "2"))) as pool:
        for n, sid in enumerate(pool.imap_unordered(one, [(out, sid, fs, keep) for sid, fs in sorted(by.items())])):
            if n % 100 == 0: print(n, sid, flush=True)


def one(job):
    out, sid, fs, keep = job
    if True:
        p = os.path.join(out, sid + ".npz")
        old = None
        if os.path.exists(p):
            z = np.load(p); old = pd.DataFrame({k: z[k] for k in ("day", "fz", "pk")})
        parts = [x for x in (reduce_file(f) for f in fs) if x is not None]
        if old is not None:
            yrs = {int(os.path.basename(os.path.dirname(f))) for f in fs}
            oy = (EPOCH + pd.to_timedelta(old.day, unit="D")).dt.year
            parts.insert(0, old[~oy.isin(yrs)])      # a re-fetched year replaces the old one
        if parts:
            d = pd.concat(parts).groupby("day").max().reset_index()
            np.savez_compressed(p + ".tmp.npz", day=d.day.values.astype(np.int32),
                                fz=d.fz.values.astype(np.uint8), pk=d.pk.values.astype(np.uint8))
            os.replace(p + ".tmp.npz", p)
        if not keep:
            for f in fs: os.remove(f)
    return sid


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--keep" in sys.argv)
