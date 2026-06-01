import os


def safe_output_path(output_path):
    """Return an unused path by appending _vN when a file already exists."""
    if not os.path.exists(output_path):
        return output_path

    base, ext = os.path.splitext(output_path)
    counter = 2
    while True:
        candidate = f"{base}_v{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def is_supported_file(path, extensions):
    return os.path.isfile(path) and path.lower().endswith(extensions)
