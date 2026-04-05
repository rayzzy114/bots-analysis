def normalize_support(value: str | None, default_username: str = "luckyexchangesupport") -> tuple[str, str]:

    if not value:

        username = default_username

        return username, f"https://t.me/{username}"


    v = value.strip()

    if v.startswith("@"):

        username = v[1:] or default_username

        return username, f"https://t.me/{username}"


    if v.startswith("http://") or v.startswith("https://"):

        v = v.split("://", 1)[1]

        v = v.split("/", 1)[1] if "/" in v else ""

        username = v.split("/", 1)[0] if v else default_username

        username = username.split("?", 1)[0]

        return username, f"https://t.me/{username}"


    if v.startswith("t.me/") or v.startswith("telegram.me/"):

        v = v.split("/", 1)[1]

        username = v.split("/", 1)[0] if v else default_username

        username = username.split("?", 1)[0]

        return username, f"https://t.me/{username}"


    if "/" not in v:

        username = v or default_username

        return username, f"https://t.me/{username}"


    return default_username, f"https://t.me/{default_username}"

