def format_text(template, replacements):
    text = template
    for key, value in replacements.items():
        # What happens if value is missing/None? 
        # The code usually assumes value is string-able.
        text = text.replace(f"{{{key}}}", str(value))
    return text

print(format_text("Contact: {operator}", {"wrong_key": "admin"}))
