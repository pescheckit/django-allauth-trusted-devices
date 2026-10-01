import re

from django.utils.translation import gettext as _

# Order matters: Edge and Opera also announce Chrome, Chrome also announces Safari.
_BROWSERS = [
    ("Edge", r"Edg(e|A|iOS)?/"),
    ("Opera", r"OPR/|Opera"),
    ("Samsung Internet", r"SamsungBrowser/"),
    ("Firefox", r"Firefox/|FxiOS/"),
    ("Chrome", r"Chrome/|CriOS/"),
    ("Safari", r"Safari/"),
]
_SYSTEMS = [
    ("iOS", r"iPhone|iPad|iPod"),
    ("Android", r"Android"),
    ("Windows", r"Windows"),
    ("macOS", r"Macintosh|Mac OS X"),
    ("ChromeOS", r"CrOS"),
    ("Linux", r"Linux"),
]


def _match(table, user_agent):
    for name, pattern in table:
        if re.search(pattern, user_agent):
            return name
    return None


def describe_user_agent(user_agent: str) -> str:
    """Short human label such as "Firefox on Linux". Deliberately coarse; no dependency."""
    user_agent = user_agent or ""
    browser = _match(_BROWSERS, user_agent)
    system = _match(_SYSTEMS, user_agent)
    if browser and system:
        return _("%(browser)s on %(system)s") % {"browser": browser, "system": system}
    return browser or system or _("Unknown device")
