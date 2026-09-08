def parse(text, strict=False):
    return dict(l.split("=",1) for l in text.splitlines() if "=" in l)
