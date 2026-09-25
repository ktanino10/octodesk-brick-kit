"""Unauthenticated GET/hash checks for the single authorized public destination."""
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from common import ROOT, OUT, BUILD, read_json, sha256, write_json
from publication import config


def fetch_verified(url, expected_hash=None, expected_bytes=None, attempts=5):
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "octodesk-public-verification/1.0",
                                            "Cache-Control": "no-cache"})
            with urlopen(request, timeout=90) as response:
                body = response.read()
                assert response.status == 200, f"HTTP {response.status}"
                actual_hash = hashlib.sha256(body).hexdigest()
                assert expected_hash is None or actual_hash == expected_hash, "Downloaded content hash mismatch"
                assert expected_bytes is None or len(body) == expected_bytes, "Downloaded size mismatch"
                return body, {"url": url, "status": 200, "bytes": len(body), "sha256": actual_hash,
                              "content_type": response.headers.get("Content-Type"),
                              "redirect_host": urlsplit(response.url).hostname,
                              "authenticated": False}
        except (HTTPError, TimeoutError, AssertionError) as error:
            last_error = f"{type(error).__name__}: {getattr(error, 'code', None) or str(error).split('?')[0]}"
            if isinstance(error, HTTPError) and error.code not in (404, 429, 500, 502, 503, 504):
                break
            if attempt < attempts - 1:
                time.sleep(12 + attempt * 6)
    raise RuntimeError(f"Public GET failed for {urlsplit(url).path}: {last_error}")


def main():
    publication = config()
    repository = publication["repository"].removeprefix("https://github.com/")
    raw, repo_get = fetch_verified(f"https://api.github.com/repos/{repository}")
    repo = json.loads(raw)
    assert repo["full_name"] == repository and repo["private"] is False
    verified = [repo_get]
    stage = BUILD / "pages"
    for name in ("index.html", "assets/guide.js", "assets/data.js", "media/hero.png",
                 "media/assembly.mp4", "media/assembly.webm", "docs/assembly-manual.pdf",
                 "coupons/01-loose-pair-NOT_SLICED.3mf", "cad/Octodesk-r1.FCStd",
                 "plates/O-green-01-NOT_SLICED.3mf", "checksums.sha256"):
        local = stage / name
        _, entry = fetch_verified(urljoin(publication["pages"], name), sha256(local), local.stat().st_size)
        verified.append(entry)
        print("PUBLIC_GET_VERIFIED", name, entry["bytes"], flush=True)
    receipt = read_json(ROOT / "dist" / "release-receipt.json")
    _, asset = fetch_verified(publication["archive_url"], receipt["sha256"], receipt["bytes"])
    verified.append(asset)
    print("RELEASE_ZIP_GET_VERIFIED", asset["bytes"], flush=True)
    write_json(BUILD / "public-hosting.json", {
        "status": "PASS", "checked_at": datetime.now(timezone.utc).isoformat(),
        "repository_is_public": True, "authenticated_downloads": False,
        "publication": publication, "resources": verified,
    })


if __name__ == "__main__":
    main()
