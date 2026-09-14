from stores.jumia import JumiaConnector
from stores.btech import BtechConnector
from stores.twob import TwoBConnector
from stores.raya import RayaConnector
from stores.carrefour import CarrefourConnector
from stores.dream2000 import Dream2000Connector
from stores.amazon import AmazonConnector
from stores.noon import NoonConnector
from stores.browser_fallback import RaneenConnector

CONNECTORS = {
    "jumia": JumiaConnector,
    "amazon": AmazonConnector,
    "noon": NoonConnector,
    "btech": BtechConnector,
    "2b": TwoBConnector,
    "raya": RayaConnector,
    "carrefour": CarrefourConnector,
    "dream2000": Dream2000Connector,
    "raneen": RaneenConnector,
}
