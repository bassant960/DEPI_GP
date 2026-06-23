from PIL import Image

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png"
}

MAX_SIZE = 5 * 1024 * 1024


def validate_image(file):

    extension = (
        file.filename
        .split(".")[-1]
        .lower()
    )

    if extension not in ALLOWED_EXTENSIONS:
        return False, "Only JPG, JPEG and PNG are allowed"

    content = file.file.read()

    if len(content) > MAX_SIZE:
        return False, "Image size must be less than 5MB"

    file.file.seek(0)

    try:

        image = Image.open(file.file)

        width, height = image.size

        if width < 300 or height < 300:
            return False, "Image dimensions are too small"

        image.verify()

    except Exception:
        return False, "Invalid image file"

    file.file.seek(0)

    return True, "Valid image"
