import os


def public_base_url(default: str = "http://localhost:3000") -> str:
    """Public base URL of the deployed app, for links sent outside the app
    (invite links, iCal feed URLs).

    NEXT_PUBLIC_APP_URL wins (custom domains); on Vercel fall back to the
    stable production domain, then the per-deployment domain.
    """
    url = (
        os.environ.get("NEXT_PUBLIC_APP_URL")
        or os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
        or os.environ.get("VERCEL_URL")
        or default
    )
    if not url.startswith("http"):
        url = f"https://{url}"
    return url.rstrip("/")
