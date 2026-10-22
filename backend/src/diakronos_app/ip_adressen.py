"""IP-Eingaben fuer den Sperrstore parsen, ohne Muell-Kennungen anzulegen."""

from ipaddress import IPv4Address, IPv6Address, ip_address


def parse_ip(wert: str | None) -> IPv4Address | IPv6Address | None:
    """Ungueltig ist nicht vertrauenswuerdig, aber auch keine IP-Kennung.

    IPv4-mapped IPv6 und unterschiedliche IPv6-Schreibweisen muessen dieselbe
    Sperre treffen. Eine IPv6-Zonenkennung benennt das lokale Interface,
    nicht einen anderen Absender; sie darf keinen neuen Zaehler erzeugen.
    """
    try:
        adresse = ip_address((wert or "").strip())
    except ValueError:
        return None
    if isinstance(adresse, IPv6Address):
        if adresse.ipv4_mapped is not None:
            return adresse.ipv4_mapped
        if adresse.scope_id is not None:
            return IPv6Address(str(adresse).split("%", 1)[0])
    return adresse
