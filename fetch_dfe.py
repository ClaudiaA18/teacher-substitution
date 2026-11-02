import io
import pathlib
import sys
import urllib.request
import zipfile

SRC = {
    "2024": ("csv", "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/"
                    "aa13e99e-534c-4f70-9c43-c7f9544296b3/csv",
             "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/"
             "aa13e99e-534c-4f70-9c43-c7f9544296b3"),
    "2025": ("zip", "https://content.explore-education-statistics.service.gov.uk/api/releases/"
                    "32476c77-5ff3-4efb-ad1e-a2173e74a4d4/files?fromPage=ReleaseDownloads",
             "https://explore-education-statistics.service.gov.uk/find-statistics/school-workforce-in-england/2025"),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def main():
    root = pathlib.Path("data/dfe")
    for year, (kind, url, page) in SRC.items():
        out = root / year
        out.mkdir(parents=True, exist_ok=True)
        print(f"[{year}] downloading...")
        try:
            data = get(url)
        except Exception as e:
            print(f"[{year}] FAILED: {e}\n  download manually from: {page}\n  and unzip into: {out}")
            continue
        if data[:2] == b"PK":
            zipfile.ZipFile(io.BytesIO(data)).extractall(out)
        elif data.lstrip()[:1] == b"<":
            print(f"[{year}] got a web page, not data\n  download manually from: {page}\n  and unzip into: {out}")
            continue
        else:
            (out / "teacher_sickness_absence_school_level.csv").write_bytes(data)
        hits = [p for p in out.rglob("*.csv") if "absence" in p.name.lower()]
        print(f"[{year}] {len(hits)} absence file(s):")
        for p in hits:
            print("   ", p)
    sys.exit(0)


if __name__ == "__main__":
    main()
