# 🔧 Configuration & ⚙️ Customization

## Fonts

* Download **Montserrat** and **Roboto Mono** from Google Fonts and extract them into the project’s `assets/fonts/` folder.
* Copy the `.ttf` files (Regular, Bold, Italic, SemiBold, etc.) into their respective `static/` directories.
* Ensure that the filenames match those declared in the `FONTS` registry inside `config.py`.
* To use another font, add it under `assets/fonts/` and extend the `FONTS` dictionary with its styles and file paths.

👉 [Download fonts here](https://fonts.google.com/share?selection.family=Montserrat:ital,wght@0,100..900;1,100..900|Roboto+Mono:ital,wght@0,100..700;1,100..700)

## Branding & Layout

In `servers/fel_mcp_server/config.py`, you can customize:

* **Brand colors** (primary, secondary, gray scales).
* **Layout parameters** such as QR size, top bar height, logo dimensions, and global font size.
* **Theme selection** (`light` or `dark`) via `.env`.
* **Paths** for XML input, logo, and PDF output (all configurable through `.env`).

### Company Information

* Set **footer details** like website, phone number, and email through `.env`.
