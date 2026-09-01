"""Palety kolorow uzywane przy rysowaniu map."""
import colorsys


def distinct_colors(n):
    colors = []
    for i in range(n):
        h = (i * 0.61803398875) % 1.0  # golden ratio - dobre rozproszenie odcieni
        r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.92)
        colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
    return colors


FIXED_4_COLORS = {
    "niebieski": "#2b6cff",
    "zielony": "#39d353",
    "bialy": "#f4f4f4",
    "zolty": "#ffd91a",
}
FIXED_4_ORDER = ["niebieski", "zielony", "bialy", "zolty"]
