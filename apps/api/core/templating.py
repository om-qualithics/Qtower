def substitute(template: str, context: dict[str, str]) -> str:
    # Plain {{var}} find/replace, not str.format() - admin-authored text
    # (an email template, an AI prompt) may contain a stray literal "{"
    # (e.g. "team{s}"), which format() would crash on. Never raises on
    # unknown text.
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result
