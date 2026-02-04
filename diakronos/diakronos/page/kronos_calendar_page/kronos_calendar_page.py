def get_context(context):
    context.no_cache = 1
    context.title = "Kronos Kalender"

    # Wir laden unsere CSS explizit – aber wir brauchen sie nicht mehr, weil wir inline/link nutzen
    context.add_css = []  # leer lassen
    context.add_js = []   # leer lassen, wir laden selbst

    # Optional: Desk-Elemente verstecken
    context.no_navbar = 1
    context.no_sidebar = 1

    return context