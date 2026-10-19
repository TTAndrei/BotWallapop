import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wallabot.api import extract_items, parse_item
from wallabot.config import Messages, load_messages, load_searches
from wallabot.filters import ItemFilter, Rules, normalize
from wallabot.models import Item

EXAMPLE = Path(__file__).resolve().parent.parent / "busquedas.example.toml"


def item(title, price=300, description="", **kw):
    return Item(id=title, title=title, description=description, price=price, **kw)


class NormalizeTest(unittest.TestCase):
    def test_units_and_spacing(self):
        for text in ("RTX 3060 12GB", "rtx3060 12 gb", "RTX-3060 (12G)", "RTX 3060 12 gigas", "RTX 3060 12Gb"):
            self.assertIn(" 3060 12gb ", normalize(text), text)

    def test_accents_and_split_suffix(self):
        self.assertEqual(normalize("Portátil RTX3060Ti"), " portatil rtx 3060 ti ")

    def test_gddr_is_not_a_unit(self):
        self.assertIn(" 12gb gddr 6 ", normalize("12G GDDR6"))


class ExampleConfigTest(unittest.TestCase):
    """Comprueba la búsqueda de ejemplo de la 3060 12GB contra anuncios típicos."""

    @classmethod
    def setUpClass(cls):
        search = next(s for s in load_searches(EXAMPLE) if s.name == "RTX 3060 12GB")
        cls.filter = ItemFilter(search.rules)

    def assertAccepted(self, it):
        self.assertIsNone(self.filter.rejection_reason(it), it.title)

    def assertRejected(self, it):
        self.assertIsNotNone(self.filter.rejection_reason(it), it.title)

    def test_good_listings(self):
        self.assertAccepted(item("MSI RTX 3060 Ventus 2X 12GB"))
        self.assertAccepted(item("Gigabyte GeForce RTX3060 Gaming OC 12G"))
        self.assertAccepted(item("Tarjeta gráfica RTX 3060 12 GB con caja original"))
        self.assertAccepted(item("Nvidia RTX 3060", description="Versión de 12gb, funciona perfecta"))
        self.assertAccepted(item("Tarjeta Gráfica RTX 3060 DE 12GB con Ventilador"))

    def test_boxes_and_accessories(self):
        self.assertRejected(item("Caja RTX 3060 12GB"))
        self.assertRejected(item("Caja vacía RTX 3060 12GB", price=250))
        self.assertRejected(item("RTX 3060 12GB", price=250, description="Vendo solo la caja, sin gráfica"))
        self.assertRejected(item("Backplate RTX 3060 12GB"))
        self.assertRejected(item("Ventiladores para RTX 3060 12GB"))

    def test_other_variants(self):
        self.assertRejected(item("RTX 3060 8GB"))
        self.assertRejected(item("RTX 3060 Ti 8GB"))
        self.assertRejected(item("RTX 3060Ti Founders"))
        self.assertRejected(item("Nvidia RTX 3060", description="la de 8 gb"))
        self.assertRejected(item("RTX 3070 / 3060 12GB"))

    def test_full_pcs(self):
        self.assertRejected(item("PC Gaming RTX 3060 12GB Ryzen 5 5600", price=300))
        self.assertRejected(item("Ordenador gaming i5 3060 12gb", price=200))
        self.assertRejected(item("Portátil MSI RTX 3060", price=230))
        self.assertRejected(item("Torre gamer 3060 12GB 16GB RAM", price=230))

    def test_wanted_and_broken(self):
        self.assertRejected(item("Busco RTX 3060 12GB"))
        self.assertRejected(item("RTX 3060 12GB averiada"))
        self.assertRejected(item("RTX 3060 12GB", description="Tiene artefactos en pantalla"))

    def test_price_range(self):
        self.assertRejected(item("RTX 3060 12GB", price=60))
        self.assertRejected(item("RTX 3060 12GB", price=550))


class RulesTest(unittest.TestCase):
    def test_alternatives_regex_and_reasons(self):
        f = ItemFilter(Rules(require=[["oled", "re:\\blcd\\b"]], exclude_title=["funda"]))
        self.assertIsNone(f.rejection_reason(item("Steam Deck OLED 512")))
        self.assertIsNone(f.rejection_reason(item("Steam Deck LCD")))
        self.assertIn("falta", f.rejection_reason(item("Steam Deck 64")))
        self.assertIn("funda", f.rejection_reason(item("Funda Steam Deck OLED")))

    def test_word_boundaries(self):
        f = ItemFilter(Rules(exclude_title=["ti"]))
        self.assertIsNone(f.rejection_reason(item("Tienda oficial RTX 3060")))
        self.assertIsNotNone(f.rejection_reason(item("RTX 3060 Ti")))

    def test_reserved_shipping_age(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        f = ItemFilter(Rules(shipping_only=True, max_age_days=7))
        self.assertEqual(f.rejection_reason(item("x", reserved=True, shipping=True)), "reservado")
        self.assertEqual(f.rejection_reason(item("x", shipping=False)), "sin envío")
        old = item("x", shipping=True, created_at=now - timedelta(days=10))
        self.assertIn("antiguo", f.rejection_reason(old, now=now))


class ParseTest(unittest.TestCase):
    def test_current_format(self):
        data = {"data": {"section": {"payload": {"items": [{
            "id": "abc", "title": "RTX 3060 12GB", "description": "como nueva",
            "price": {"amount": 175.0, "currency": "EUR"},
            "reserved": {"flag": False},
            "shipping": {"item_is_shippable": True, "user_allows_shipping": True},
            "images": [{"urls": {"small": "s.jpg", "medium": "m.jpg", "big": "b.jpg"}}],
            "location": {"city": "Madrid"},
            "web_slug": "rtx-3060-12gb-123", "created_at": 1767225600000,
        }]}}}, "meta": {"next_page": "tok"}}
        [raw] = extract_items(data)
        it = parse_item(raw)
        self.assertEqual((it.id, it.price, it.city, it.image), ("abc", 175.0, "Madrid", "m.jpg"))
        self.assertTrue(it.shipping)
        self.assertFalse(it.reserved)
        self.assertEqual(it.url, "https://es.wallapop.com/item/rtx-3060-12gb-123")
        self.assertEqual(it.created_at.year, 2026)

    def test_legacy_format(self):
        data = {"search_objects": [{
            "id": 7, "title": "RTX 3060", "price": 150, "flags": {"reserved": True},
            "shipping_allowed": False, "web_slug": "rtx-3060-7", "images": [{"medium": "m.jpg"}],
        }]}
        it = parse_item(extract_items(data)[0])
        self.assertEqual((it.id, it.price, it.image), ("7", 150.0, "m.jpg"))
        self.assertTrue(it.reserved)


class MessagesTest(unittest.TestCase):
    def test_shipping_question_only_outside_catalonia(self):
        m = load_messages(EXAMPLE)
        barcelona = item("MSI RTX 3060 12GB", postal_code="08001")
        sevilla = item("Zotac RTX 3060 12GB", postal_code="41001")
        portugal = item("ASUS RTX 3060 12GB", postal_code="08100", country="PT")
        self.assertTrue(m.is_local(barcelona))
        self.assertNotIn("envi", m.for_item(barcelona))
        self.assertIn("la gráfica", m.for_item(barcelona))
        self.assertIn("enviarla", m.for_item(sevilla))
        self.assertFalse(m.is_local(portugal))

    def test_placeholders(self):
        m = Messages(local="{titulo} a {precio}")
        self.assertEqual(m.for_item(item("RTX", price=250, postal_code="08001")), "RTX a 250 €")


if __name__ == "__main__":
    unittest.main()
