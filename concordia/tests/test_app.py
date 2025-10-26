from concordia.app.main import app


def test_app_title():
    assert app.title == "Concordia API"


def test_router_tags_present():
    tags = {tag for route in app.routes for tag in getattr(route, "tags", [])}
    assert {"events", "sessions", "metrics", "view"}.issubset(tags)
