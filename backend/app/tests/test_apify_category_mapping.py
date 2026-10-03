from app.service.planning_json_poi_service import (
    GoogleMapsPlaceMapper,
    map_apify_categories,
)


def test_maps_polish_apify_categories_to_internal_categories():
    assert map_apify_categories(["Sala koncertowa", "Filharmonia"]) == [
        "music",
        "concert",
    ]
    assert map_apify_categories(["Zamek"]) == [
        "castle",
        "historic",
        "architecture",
        "landmark",
    ]
    assert map_apify_categories(["Muzeum sztuki"]) == ["museum", "art"]


def test_does_not_confuse_parking_with_park_or_music_school_with_attraction():
    assert map_apify_categories(["Parking", "Parkuj i Jedź"]) == []
    assert map_apify_categories(["Szkoła muzyczna", "Nauczyciel muzyki"]) == []


def test_mapper_keeps_original_categories_and_appends_internal_tags():
    poi = GoogleMapsPlaceMapper().to_poi(
        {
            "placeId": "music-place",
            "title": "Filharmonia testowa",
            "location": {"lat": 50.0647, "lng": 19.945},
            "categoryName": "Sala koncertowa",
            "categories": ["Filharmonia"],
        }
    )

    assert poi is not None
    assert poi.types == [
        "Sala koncertowa",
        "Filharmonia",
        "music",
        "concert",
    ]
