from pathlib import Path
import json
import unicodedata

import pandas as pd
import geopandas as gpd
import folium

from branca.element import MacroElement, Template
from shapely.geometry import LineString, mapping


# =========================================================
# 1. PUTANJE
# =========================================================

ROOT = Path(__file__).resolve().parent.parent

BOUNDARIES_DIR = ROOT / "data" / "boundaries"
STATIONS_DIR = ROOT / "data" / "stations"
GRAPHICS_DIR = ROOT / "graphics"

MUNICIPALITIES_FILE = (
    BOUNDARIES_DIR
    / "serbia_municipalities.geojson"
)

STATIONS_FILE = (
    STATIONS_DIR
    / "meteorological_stations.csv"
)

OUTPUT_HTML = (
    GRAPHICS_DIR
    / "interaktivna_srbija_opstine.html"
)

GRAPHICS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# 2. PROVERA
# =========================================================

for file in [
    MUNICIPALITIES_FILE,
    STATIONS_FILE
]:
    if not file.exists():
        raise RuntimeError(
            f"Nedostaje fajl:\n{file}"
        )


# =========================================================
# 3. TRANSLITERACIJA
# =========================================================

CYR_TO_LAT = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
    "Ђ": "Đ", "Е": "E", "Ж": "Ž", "З": "Z", "И": "I",
    "Ј": "J", "К": "K", "Л": "L", "Љ": "Lj", "М": "M",
    "Н": "N", "Њ": "Nj", "О": "O", "П": "P", "Р": "R",
    "С": "S", "Т": "T", "Ћ": "Ć", "У": "U", "Ф": "F",
    "Х": "H", "Ц": "C", "Ч": "Č", "Џ": "Dž", "Ш": "Š",

    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "ђ": "đ", "е": "e", "ж": "ž", "з": "z", "и": "i",
    "ј": "j", "к": "k", "л": "l", "љ": "lj", "м": "m",
    "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "ћ": "ć", "у": "u", "ф": "f",
    "х": "h", "ц": "c", "ч": "č", "џ": "dž", "ш": "š",
}


def cyr_to_lat(text):
    return "".join(
        CYR_TO_LAT.get(ch, ch)
        for ch in str(text)
    )


def latin_ascii(text):
    text = (
        unicodedata.normalize(
            "NFD",
            str(text)
        )
        .replace("đ", "d")
        .replace("Đ", "D")
    )

    return "".join(
        ch
        for ch in text
        if unicodedata.category(ch) != "Mn"
    )


# =========================================================
# 4. OPSTINE
# =========================================================

print("=" * 80)
print("INTERAKTIVNA KARTA SRBIJE")
print("=" * 80)

print("\nUcitavam opstine...")

municipalities = gpd.read_file(
    MUNICIPALITIES_FILE
).to_crs("EPSG:4326")

if "Value_sc" not in municipalities.columns:
    raise RuntimeError(
        "U GeoJSON-u ne postoji kolona Value_sc."
    )

municipalities["naziv"] = (
    municipalities["Value_sc"]
    .astype(str)
    .str.title()
)

municipalities["naziv_lat"] = (
    municipalities["naziv"]
    .apply(cyr_to_lat)
)

municipalities["naziv_lat_ascii"] = (
    municipalities["naziv_lat"]
    .apply(latin_ascii)
)


# =========================================================
# 5. SPOLJNA GEOMETRIJA
# =========================================================

outer_geometry = (
    municipalities
    .geometry
    .union_all()
)

if outer_geometry.geom_type == "Polygon":
    country_polygons = [outer_geometry]

elif outer_geometry.geom_type == "MultiPolygon":
    country_polygons = list(
        outer_geometry.geoms
    )

else:
    raise RuntimeError(
        "Nepoznat tip spoljne geometrije: "
        f"{outer_geometry.geom_type}"
    )


# =========================================================
# 6. SAMO EXTERIOR ZA DEBELU GRANICU
# =========================================================

outer_features = []

for i, polygon in enumerate(
    country_polygons
):

    exterior = LineString(
        polygon.exterior.coords
    )

    outer_features.append(
        {
            "type": "Feature",
            "properties": {
                "id": i
            },
            "geometry": mapping(
                exterior
            )
        }
    )

outer_geojson = {
    "type": "FeatureCollection",
    "features": outer_features
}


# =========================================================
# 7. BOUNDS
# =========================================================

minx, miny, maxx, maxy = (
    municipalities.total_bounds
)

center_lat = (
    miny + maxy
) / 2.0

center_lon = (
    minx + maxx
) / 2.0

country_bounds = [
    [float(miny), float(minx)],
    [float(maxy), float(maxx)]
]


# =========================================================
# 8. STANICE
# =========================================================

print(
    "Ucitavam meteoroloske stanice..."
)

stations = pd.read_csv(
    STATIONS_FILE
)

required_columns = {
    "station",
    "latitude",
    "longitude"
}

if not required_columns.issubset(
    stations.columns
):
    raise RuntimeError(
        "CSV mora imati kolone: "
        "station, latitude, longitude"
    )

print(
    "Broj stanica:",
    len(stations)
)


# =========================================================
# 9. KRACA IMENA STANICA
# =========================================================

display_names = {
    "Нови Сад – Римски Шанчеви":
        "Нови Сад",

    "Београд – Врачар":
        "Београд",

    "Смедеревска Паланка":
        "См. Паланка",

    "Сремска Митровица":
        "Ср. Митровица",

    "Банатски Карловац":
        "Бан. Карловац",

    "Велико Градиште":
        "В. Градиште",

    "Косовска Митровица":
        "Кос. Митровица",
}


# =========================================================
# 10. POLOZAJI NATPISA
# =========================================================

offsets = {
    "Палић": (-0.08, -0.09),
    "Сомбор": (0.08, 0.00),
    "Нови Сад – Римски Шанчеви": (0.10, 0.04),
    "Кикинда": (-0.08, -0.02),
    "Зрењанин": (0.10, 0.04),
    "Сремска Митровица": (0.07, -0.04),
    "Банатски Карловац": (-0.07, 0.04),
    "Вршац": (-0.08, -0.03),

    "Београд – Врачар": (0.07, 0.04),
    "Лозница": (0.08, 0.00),
    "Ваљево": (0.07, 0.02),
    "Пожега": (0.07, 0.02),
    "Смедеревска Паланка": (-0.07, 0.03),
    "Крагујевац": (-0.10, 0.02),
    "Велико Градиште": (-0.08, -0.07),
    "Ћуприја": (0.10, 0.02),
    "Краљево": (0.07, 0.02),
    "Крушевац": (0.10, 0.035),

    "Црни Врх": (-0.07, 0.03),
    "Неготин": (-0.08, -0.02),

    "Златибор": (0.07, 0.02),
    "Сјеница": (0.07, 0.02),
    "Копаоник": (0.07, 0.02),

    "Ниш": (0.07, 0.02),
    "Лесковац": (-0.10, 0.03),
    "Димитровград": (-0.10, 0.045),
    "Врање": (-0.08, 0.04),

    "Приштина": (0.07, -0.03),
    "Косовска Митровица": (0.07, 0.03),
}


# =========================================================
# 11. PRIORITET NATPISA STANICA
# =========================================================

station_core = {
    "Нови Сад – Римски Шанчеви",
    "Београд – Врачар",
    "Крагујевац",
    "Краљево",
    "Ниш",
    "Приштина",
}

station_level2 = {
    "Сомбор",
    "Зрењанин",
    "Сремска Митровица",
    "Лозница",
    "Ваљево",
    "Крушевац",
    "Неготин",
    "Врање",
}

station_level3 = {
    "Палић",
    "Кикинда",
    "Банатски Карловац",
    "Вршац",
    "Пожега",
    "Смедеревска Паланка",
    "Велико Градиште",
    "Ћуприја",
    "Црни Врх",
    "Златибор",
    "Сјеница",
    "Копаоник",
    "Лесковац",
    "Димитровград",
    "Косовска Митровица",
}


# =========================================================
# 12. MAPA
# =========================================================

m = folium.Map(
    location=[
        center_lat,
        center_lon
    ],
    zoom_start=7,
    tiles=None,
    control_scale=True,
    zoom_control=True,
    prefer_canvas=True,
    min_zoom=5,
    max_zoom=18
)


# =========================================================
# 13. BASEMAP SLOJEVI
#
# Fizicko-geografska = OpenTopoMap
# Svetla = CARTO Positron
# Satelit = Esri World Imagery
# =========================================================

topo = folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/"
        "ArcGIS/rest/services/World_Topo_Map/"
        "MapServer/tile/{z}/{y}/{x}"
    ),
    attr="Tiles © Esri",
    name="Физичко-географска",
    overlay=False,
    control=True,
    show=True,
    opacity=0.85,
    max_zoom=18
)

topo.add_to(
    m
)


light = folium.TileLayer(
    tiles=(
        "https://{s}.basemaps.cartocdn.com/"
        "light_all/{z}/{x}/{y}{r}.png"
    ),
    attr="© OpenStreetMap contributors © CARTO",
    name="Светла",
    overlay=False,
    control=True,
    show=False,
    opacity=0.78,
    max_zoom=20
)

light.add_to(
    m
)


satellite = folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/"
        "ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}"
    ),
    attr="Tiles © Esri",
    name="Сателитска",
    overlay=False,
    control=True,
    show=False,
    opacity=0.78,
    max_zoom=18
)

satellite.add_to(
    m
)


# =========================================================
# 14. OPSTINE
# =========================================================

def municipality_style(
    feature
):
    return {
        "fillColor": "#FFFFFF",
        "fillOpacity": 0.02,
        "color": "#777777",
        "weight": 0.70,
    }


def municipality_highlight(
    feature
):
    return {
        "fillColor": "#DCECF7",
        "fillOpacity": 0.48,
        "color": "#222222",
        "weight": 1.8,
    }


municipality_layer = folium.GeoJson(
    municipalities,
    name="Општине",
    style_function=
        municipality_style,
    highlight_function=
        municipality_highlight,
    tooltip=folium.GeoJsonTooltip(
        fields=[
            "naziv"
        ],
        aliases=[
            "Општина:"
        ],
        sticky=True
    ),
    popup=folium.GeoJsonPopup(
        fields=[
            "naziv",
            "Municipality_DOM_ID"
        ],
        aliases=[
            "Општина:",
            "Шифра:"
        ]
    ),
    popup_keep_highlighted=True
).add_to(
    m
)


# =========================================================
# 15. SPOLJNA GRANICA
# =========================================================

folium.GeoJson(
    outer_geojson,
    name="Спољна граница",
    style_function=lambda feature: {
        "color": "#000000",
        "weight": 2.6,
        "opacity": 1.0,
    },
    interactive=False,
    control=False
).add_to(
    m
)


# =========================================================
# 16. TACKE METEOROLOSKIH STANICA
# =========================================================

station_points = folium.FeatureGroup(
    name="Метеоролошке станице",
    show=True,
    control=True
)


# =========================================================
# 17. GRUPE NATPISA STANICA
# =========================================================

labels_core = folium.FeatureGroup(
    name="station_core",
    show=True,
    control=False
)

labels_level2 = folium.FeatureGroup(
    name="station_level2",
    show=True,
    control=False
)

labels_level3 = folium.FeatureGroup(
    name="station_level3",
    show=True,
    control=False
)

labels_rest = folium.FeatureGroup(
    name="station_rest",
    show=True,
    control=False
)


# =========================================================
# 18. DODAVANJE STANICA
# =========================================================

for _, row in stations.iterrows():

    original_name = str(
        row["station"]
    )

    station_name = (
        display_names.get(
            original_name,
            original_name
        )
    )

    lat = float(
        row["latitude"]
    )

    lon = float(
        row["longitude"]
    )

    elevation = row.get(
        "elevation_m"
    )

    tooltip_text = (
        f"<b>{station_name}</b>"
    )

    if pd.notna(
        elevation
    ):
        tooltip_text += (
            f"<br>Надморска висина: "
            f"{float(elevation):.0f} m"
        )

    popup_text = (
        f"<b>{station_name}</b><br>"
        f"Географска ширина: "
        f"{lat:.3f}° N<br>"
        f"Географска дужина: "
        f"{lon:.3f}° E"
    )

    if pd.notna(
        elevation
    ):
        popup_text += (
            f"<br>Надморска висина: "
            f"{float(elevation):.0f} m"
        )

    folium.CircleMarker(
        location=[
            lat,
            lon
        ],
        radius=3.5,
        color="black",
        weight=1,
        fill=True,
        fill_color="black",
        fill_opacity=1,
        tooltip=folium.Tooltip(
            tooltip_text,
            sticky=True
        ),
        popup=folium.Popup(
            popup_text,
            max_width=260
        )
    ).add_to(
        station_points
    )

    dx, dy = offsets.get(
        original_name,
        (0.06, 0.02)
    )

    if dx < 0:
        text_align = "right"
        transform = "translateX(-100%)"
    else:
        text_align = "left"
        transform = "none"

    label_html = f"""
    <div class="station-label"
         style="
             text-align:{text_align};
             transform:{transform};
         ">
        {station_name}
    </div>
    """

    marker = folium.Marker(
        location=[
            lat + dy,
            lon + dx
        ],
        icon=folium.DivIcon(
            icon_size=(
                140,
                20
            ),
            icon_anchor=(
                0,
                10
            ),
            html=label_html
        ),
        interactive=False
    )

    if original_name in station_core:
        marker.add_to(
            labels_core
        )

    elif original_name in station_level2:
        marker.add_to(
            labels_level2
        )

    elif original_name in station_level3:
        marker.add_to(
            labels_level3
        )

    else:
        marker.add_to(
            labels_rest
        )


station_points.add_to(m)
labels_core.add_to(m)
labels_level2.add_to(m)
labels_level3.add_to(m)
labels_rest.add_to(m)


# =========================================================
# 19. PRIVREMENE REPREZENTATIVNE TACKE OPSTINA
# =========================================================

municipality_points_group = folium.FeatureGroup(
    name="Општински центри – привремено",
    show=True,
    control=False
)

municipality_labels_group = folium.FeatureGroup(
    name="Називи општина – крупан zoom",
    show=True,
    control=False
)

municipality_rep_points = (
    municipalities
    .geometry
    .representative_point()
)

for idx, row in municipalities.iterrows():

    point = municipality_rep_points.loc[
        idx
    ]

    mun_name = str(
        row["naziv"]
    )

    folium.CircleMarker(
        location=[
            point.y,
            point.x
        ],
        radius=2.0,
        color="#666666",
        weight=1,
        fill=True,
        fill_color="#777777",
        fill_opacity=0.85,
        tooltip=folium.Tooltip(
            f"Општина: {mun_name}",
            sticky=True
        )
    ).add_to(
        municipality_points_group
    )

    folium.Marker(
        location=[
            point.y,
            point.x
        ],
        icon=folium.DivIcon(
            icon_size=(
                150,
                18
            ),
            icon_anchor=(
                -4,
                9
            ),
            html=(
                '<div class="municipality-label">'
                f'{mun_name}'
                '</div>'
            )
        ),
        interactive=False
    ).add_to(
        municipality_labels_group
    )


municipality_points_group.add_to(
    m
)

municipality_labels_group.add_to(
    m
)


# =========================================================
# 20. SEARCH PODACI
# =========================================================

search_data = []

for _, row in municipalities.iterrows():

    bx1, by1, bx2, by2 = (
        row.geometry.bounds
    )

    search_data.append(
        {
            "name":
                str(
                    row["naziv"]
                ),

            "cyr":
                str(
                    row["naziv"]
                ).lower(),

            "lat":
                str(
                    row["naziv_lat"]
                ).lower(),

            "lat_ascii":
                str(
                    row["naziv_lat_ascii"]
                ).lower(),

            "bounds": [
                [
                    float(by1),
                    float(bx1)
                ],
                [
                    float(by2),
                    float(bx2)
                ]
            ]
        }
    )


search_data_json = json.dumps(
    search_data,
    ensure_ascii=False
)


# =========================================================
# 21. CSS
# =========================================================

css = """
<style>

html, body {
    background: white !important;
}

.leaflet-container {
    background: #eef2f4 !important;
    font-family: Arial, sans-serif;
}

.leaflet-tooltip {
    font-size: 13px;
    background: rgba(255,255,255,0.96);
    border: 1px solid #777;
    color: #111;
    box-shadow: none;
}

.station-label {
    background: transparent;
    border: none;
    box-shadow: none;
    color: #111;
    font-size: 12px;
    font-weight: 550;
    padding: 0;
    white-space: nowrap;
    pointer-events: none;

    text-shadow:
        -1px -1px 0 rgba(255,255,255,0.90),
         1px -1px 0 rgba(255,255,255,0.90),
        -1px  1px 0 rgba(255,255,255,0.90),
         1px  1px 0 rgba(255,255,255,0.90);
}

.municipality-label {
    background: transparent;
    border: none;
    box-shadow: none;
    color: #555;
    font-size: 10px;
    font-weight: 400;
    padding: 1px 2px;
    white-space: nowrap;
    pointer-events: none;
}

.map-search-box {
    position: absolute;
    top: 75px;
    left: 10px;
    width: 300px;
    z-index: 10000;
    font-family: Arial, sans-serif;
}

.map-search-input {
    box-sizing: border-box;
    width: 100%;
    padding: 8px 10px;
    border: 1px solid #777;
    border-radius: 4px;
    background: rgba(255,255,255,0.97);
    font-size: 14px;
    outline: none;
}

.map-search-results {
    display: none;
    max-height: 300px;
    overflow-y: auto;
    margin-top: 2px;
    background: rgba(255,255,255,0.99);
    border: 1px solid #999;
    border-radius: 4px;
}

.map-search-result {
    padding: 7px 9px;
    cursor: pointer;
    font-size: 13px;
}

.map-search-result:hover {
    background: #DCECF7;
}

.opacity-control {
    position: absolute;
    left: 10px;
    bottom: 28px;
    width: 245px;
    z-index: 10000;
    background: rgba(255,255,255,0.94);
    border: 1px solid #999;
    border-radius: 5px;
    padding: 7px 10px;
    font-family: Arial, sans-serif;
    font-size: 12px;
}

.opacity-slider {
    width: 150px;
    vertical-align: middle;
}

.map-title {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10000;
    background: rgba(255,255,255,0.92);
    padding: 7px 18px;
    border-radius: 5px;
    font-family: Arial, sans-serif;
    font-size: 19px;
    font-weight: bold;
    white-space: nowrap;
}

</style>
"""

m.get_root().header.add_child(
    folium.Element(
        css
    )
)


# =========================================================
# 22. DYNAMIC CONTROLS
# =========================================================

class DynamicControls(
    MacroElement
):

    def __init__(
        self,
        search_data,
        municipality_layer_name,
        topo_name,
        light_name,
        satellite_name,
        labels_core_name,
        labels_level2_name,
        labels_level3_name,
        labels_rest_name,
        municipality_points_name,
        municipality_labels_name,
    ):
        super().__init__()

        self._name = (
            "DynamicControls"
        )

        self.search_data = (
            search_data
        )

        self.municipality_layer_name = (
            municipality_layer_name
        )

        self.topo_name = (
            topo_name
        )

        self.light_name = (
            light_name
        )

        self.satellite_name = (
            satellite_name
        )

        self.labels_core_name = (
            labels_core_name
        )

        self.labels_level2_name = (
            labels_level2_name
        )

        self.labels_level3_name = (
            labels_level3_name
        )

        self.labels_rest_name = (
            labels_rest_name
        )

        self.municipality_points_name = (
            municipality_points_name
        )

        self.municipality_labels_name = (
            municipality_labels_name
        )

        self._template = Template(
r"""
{% macro html(this, kwargs) %}

<div class="map-title">
Република Србија – општине и метеоролошке станице
</div>

<div class="map-search-box">

    <input
        id="municipality-search-input"
        class="map-search-input"
        type="text"
        autocomplete="off"
        placeholder="Претрага општине / Pretraga opstine..."
    >

    <div
        id="municipality-search-results"
        class="map-search-results">
    </div>

</div>

<div class="opacity-control">

    <b>Подлога:</b>

    <input
        id="opacity-slider"
        class="opacity-slider"
        type="range"
        min="15"
        max="100"
        value="78"
    >

    <span id="opacity-value">
        78%
    </span>

</div>

{% endmacro %}


{% macro script(this, kwargs) %}

(function() {

    var map =
        {{ this._parent.get_name() }};

    var municipalitiesLayer =
        {{ this.municipality_layer_name | safe }};

    var topoLayer =
        {{ this.topo_name | safe }};

    var lightLayer =
        {{ this.light_name | safe }};

    var satelliteLayer =
        {{ this.satellite_name | safe }};

    var currentBaseLayer =
        topoLayer;

    var labelsCore =
        {{ this.labels_core_name | safe }};

    var labelsLevel2 =
        {{ this.labels_level2_name | safe }};

    var labelsLevel3 =
        {{ this.labels_level3_name | safe }};

    var labelsRest =
        {{ this.labels_rest_name | safe }};

    var municipalityPoints =
        {{ this.municipality_points_name | safe }};

    var municipalityLabels =
        {{ this.municipality_labels_name | safe }};

    var municipalityData =
        {{ this.search_data | safe }};


    // =====================================================
    // 1. ZOOM-DEPENDENT NATPISI
    // =====================================================

    function ensureOn(layer) {

        if (!map.hasLayer(layer)) {
            map.addLayer(layer);
        }

    }


    function ensureOff(layer) {

        if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }

    }


    function updateLabels() {

        var z =
            map.getZoom();


        ensureOn(
            labelsCore
        );


        if (z <= 6) {

            ensureOff(
                labelsLevel2
            );

            ensureOff(
                labelsLevel3
            );

            ensureOff(
                labelsRest
            );

        }

        else if (z === 7) {

            ensureOn(
                labelsLevel2
            );

            ensureOff(
                labelsLevel3
            );

            ensureOff(
                labelsRest
            );

        }

        else if (z === 8) {

            ensureOn(
                labelsLevel2
            );

            ensureOn(
                labelsLevel3
            );

            ensureOff(
                labelsRest
            );

        }

        else {

            ensureOn(
                labelsLevel2
            );

            ensureOn(
                labelsLevel3
            );

            ensureOn(
                labelsRest
            );

        }


        if (z >= 9) {

            ensureOn(
                municipalityPoints
            );

        }

        else {

            ensureOff(
                municipalityPoints
            );

        }


        if (z >= 11) {

            ensureOn(
                municipalityLabels
            );

        }

        else {

            ensureOff(
                municipalityLabels
            );

        }

    }


    map.on(
        "zoomend",
        updateLabels
    );

    updateLabels();


    // =====================================================
    // 2. SEARCH - ĆIRILICA + LATINICA
    // =====================================================

    var input =
        document.getElementById(
            "municipality-search-input"
        );

    var results =
        document.getElementById(
            "municipality-search-results"
        );


    function normBasic(
        text
    ) {

        return (
            text
            .toLowerCase()
            .trim()
        );

    }


    function normLatin(
        text
    ) {

        return (
            text
            .toLowerCase()
            .normalize("NFD")
            .replace(
                /[\u0300-\u036f]/g,
                ""
            )
            .replace(
                /đ/g,
                "d"
            )
            .trim()
        );

    }


    function hideResults() {

        results.innerHTML =
            "";

        results.style.display =
            "none";

    }


    function highlightMunicipality(
        item
    ) {

        if (
            municipalitiesLayer.resetStyle
        ) {

            municipalitiesLayer.resetStyle();

        }


        municipalitiesLayer.eachLayer(
            function(layer) {

                if (
                    layer.feature
                    &&
                    layer.feature.properties
                    &&
                    layer.feature.properties.naziv
                    === item.name
                ) {

                    layer.setStyle({

                        fillColor:
                            "#FFD966",

                        fillOpacity:
                            0.58,

                        color:
                            "#C75B00",

                        weight:
                            2.5

                    });


                    if (
                        layer.openTooltip
                    ) {

                        layer.openTooltip();

                    }


                    window.setTimeout(
                        function() {

                            municipalitiesLayer.resetStyle(
                                layer
                            );

                            if (
                                layer.closeTooltip
                            ) {

                                layer.closeTooltip();

                            }

                        },
                        3500
                    );

                }

            }
        );

    }


    function chooseMunicipality(
        item
    ) {

        input.value =
            item.name;

        hideResults();

        map.fitBounds(
            item.bounds,
            {
                padding:
                    [35, 35],

                maxZoom:
                    11
            }
        );

        highlightMunicipality(
            item
        );

    }


    input.addEventListener(
        "input",
        function() {

            var raw =
                input.value;

            var qCyr =
                normBasic(
                    raw
                );

            var qLat =
                normLatin(
                    raw
                );


            results.innerHTML =
                "";


            if (
                qCyr.length < 1
            ) {

                hideResults();

                return;

            }


            var matches =
                municipalityData

                .filter(
                    function(item) {

                        var cyr =
                            normBasic(
                                item.cyr
                            );

                        var lat =
                            normLatin(
                                item.lat
                            );

                        var ascii =
                            normLatin(
                                item.lat_ascii
                            );


                        return (

                            cyr.startsWith(
                                qCyr
                            )

                            ||

                            lat.startsWith(
                                qLat
                            )

                            ||

                            ascii.startsWith(
                                qLat
                            )

                        );

                    }
                )

                .slice(
                    0,
                    14
                );


            if (
                matches.length === 0
            ) {

                hideResults();

                return;

            }


            matches.forEach(
                function(item) {

                    var div =
                        document.createElement(
                            "div"
                        );

                    div.className =
                        "map-search-result";

                    div.textContent =
                        item.name;

                    div.onclick =
                        function() {

                            chooseMunicipality(
                                item
                            );

                        };

                    results.appendChild(
                        div
                    );

                }
            );


            results.style.display =
                "block";

        }
    );


    input.addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter"
            ) {

                var first =
                    results.querySelector(
                        ".map-search-result"
                    );

                if (
                    first
                ) {

                    first.click();

                }

            }

            if (
                event.key === "Escape"
            ) {

                hideResults();

            }

        }
    );


    document.addEventListener(
        "click",
        function(event) {

            var box =
                document.querySelector(
                    ".map-search-box"
                );

            if (
                box
                &&
                !box.contains(
                    event.target
                )
            ) {

                hideResults();

            }

        }
    );


    // =====================================================
    // 3. OPACITY TRENUTNE PODLOGE
    // =====================================================

    var slider =
        document.getElementById(
            "opacity-slider"
        );

    var opacityValue =
        document.getElementById(
            "opacity-value"
        );


    function setCurrentBaseOpacity() {

        var value =
            parseInt(
                slider.value
            );

        currentBaseLayer.setOpacity(
            value / 100.0
        );

        opacityValue.textContent =
            value + "%";

    }


    slider.addEventListener(
        "input",
        setCurrentBaseOpacity
    );


    map.on(
        "baselayerchange",
        function(event) {

            currentBaseLayer =
                event.layer;

            setCurrentBaseOpacity();

        }
    );


})();

{% endmacro %}
"""
        )


controls = DynamicControls(
    search_data=
        search_data_json,

    municipality_layer_name=
        municipality_layer.get_name(),

    topo_name=
        topo.get_name(),

    light_name=
        light.get_name(),

    satellite_name=
        satellite.get_name(),

    labels_core_name=
        labels_core.get_name(),

    labels_level2_name=
        labels_level2.get_name(),

    labels_level3_name=
        labels_level3.get_name(),

    labels_rest_name=
        labels_rest.get_name(),

    municipality_points_name=
        municipality_points_group.get_name(),

    municipality_labels_name=
        municipality_labels_group.get_name(),
)

controls.add_to(
    m
)


# =========================================================
# 23. LAYER CONTROL
# =========================================================

folium.LayerControl(
    collapsed=False
).add_to(
    m
)


# =========================================================
# 24. FIT NA SRBIJU
# =========================================================

m.fit_bounds(
    country_bounds,
    padding=(
        25,
        25
    )
)


# =========================================================
# 25. SNIMANJE
# =========================================================

m.save(
    OUTPUT_HTML
)


print("\n" + "=" * 80)
print("GOTOVO")
print("=" * 80)

print("\nInteraktivna karta:")
print(OUTPUT_HTML)

print(
    "\nBroj opstina:",
    len(municipalities)
)

print(
    "Broj meteoroloskih stanica:",
    len(stations)
)

print(
    "\nPodloge:"
)

print(
    "- Fizicko-geografska (Esri World Topographic Map)"
)

print(
    "- Svetla (CARTO)"
)

print(
    "- Satelitska (Esri)"
)

print(
    "\nNAPOMENA:"
)

print(
    "Opstinske sive tacke su i dalje representative_point() "
    "poligona, a ne proverena stvarna sedista opstina."
)
