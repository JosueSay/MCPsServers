import os
from dotenv import load_dotenv
from reportlab.lib import colors

load_dotenv()

# ---------- Brand colors ----------
ORANGE     = colors.HexColor("#fe5101")
DARK_GRAY  = colors.HexColor("#343534")
BLACK      = colors.HexColor("#000000")
WHITE      = colors.HexColor("#ffffff")
GRAY_LIGHT = colors.HexColor("#d9d9da")
GRAY_SOFT  = colors.HexColor("#8c8d8e")

# ---------- Layout (from .env, with defaults) ----------
DEFAULT_QR_SIZE        = int(os.getenv("FEL_QR_SIZE", "150"))
DEFAULT_TOP_BAR_HEIGHT = int(os.getenv("FEL_TOP_BAR_HEIGHT", "20"))

# ---------- Paths (from .env) ----------
XML_PATH   = os.getenv("FEL_XML_PATH", "./data/xml/factura.xml")
LOGO_PATH  = os.getenv("FEL_LOGO_PATH", "./data/logos/logo.jpg")
OUTPUT_PDF = os.getenv("FEL_OUTPUT_PDF", "./data/out/factura.pdf")

# ---------- Fonts & theme ----------
ACTIVE_FONT         = int(os.getenv("FEL_ACTIVE_FONT", "1"))  # 1 = Montserrat, 2 = RobotoMono
FONT_DIR_MONTSERRAT = os.getenv("FEL_FONT_DIR_MONTSERRAT", "./assets/fonts/Montserrat/static")
FONT_DIR_ROBOTOMONO = os.getenv("FEL_FONT_DIR_ROBOTOMONO", "./assets/fonts/Roboto_Mono/static")
THEME               = os.getenv("FEL_THEME", "light")

# ---------- Footer contact ----------
WEBSITE = os.getenv("FEL_WEBSITE", "https://ccinco.net")
PHONE   = os.getenv("FEL_PHONE", "(502) 2254-9885")
EMAIL   = os.getenv("FEL_EMAIL", "info@ccinco.net")

# ---------- Global typography ----------
GLOBAL_FONT_SIZE = 10
LOGO_WIDTH  = 100
LOGO_HEIGHT = 90

# ---------- Font registry ----------
FONTS = {
    1: {
        "name": "Montserrat",
        "path": FONT_DIR_MONTSERRAT,
        "files": {
            "Regular":  "Montserrat-Regular.ttf",
            "Bold":     "Montserrat-Bold.ttf",
            "Italic":   "Montserrat-Italic.ttf",
            "SemiBold": "Montserrat-SemiBold.ttf",
        },
    },
    2: {
        "name": "RobotoMono",
        "path": FONT_DIR_ROBOTOMONO,
        "files": {
            "Regular":  "RobotoMono-Regular.ttf",
            "Bold":     "RobotoMono-Bold.ttf",
            "Italic":   "RobotoMono-Italic.ttf",
            "SemiBold": "RobotoMono-SemiBold.ttf",
        },
    },
}
