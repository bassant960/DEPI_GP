import os
import uuid

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

UPLOAD_USERS = os.path.join(
    BASE_DIR,
    "uploads",
    "users"
)

UPLOAD_GENERATED = os.path.join(
    BASE_DIR,
    "uploads",
    "generated"
)

os.makedirs(
    UPLOAD_USERS,
    exist_ok=True
)

os.makedirs(
    UPLOAD_GENERATED,
    exist_ok=True
)

def save_user_image(file):

    extension = (
        file.filename
        .split(".")[-1]
        .lower()
    )

    filename = (
        str(uuid.uuid4())
        + "."
        + extension
    )

    filepath = os.path.join(
        UPLOAD_USERS,
        filename
    )

    with open(
        filepath,
        "wb"
    ) as buffer:

        buffer.write(
            file.file.read()
        )

    file.file.seek(0)

    return filepath


def save_generated_image(
    image_bytes
):

    filename = (
        str(uuid.uuid4())
        + ".jpg"
    )

    filepath = os.path.join(
        UPLOAD_GENERATED,
        filename
    )

    with open(
        filepath,
        "wb"
    ) as buffer:

        buffer.write(
            image_bytes
        )

    return f"/uploads/generated/{filename}"
