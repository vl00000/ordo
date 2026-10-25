"""ORDO server giriş nöqtəsi.

İşə salmaq (Ordo qovluğunda):
  uvicorn ordo.server:app --host 127.0.0.1 --port 8000 --workers 1 --no-server-header
--host 127.0.0.1: API yalnız bu kompüterdən əlçatandır, internetə açılmır.
--no-server-header: cavablarda hansı server proqramının işlədiyi göstərilmir.
--workers 1: eyni bazanı yalnız bir proses açmalıdır (bax: ORDO_SCHEMA.md).
ORDO_DB mühit dəyişəni bazanın yoludur (standart: ordo.db).
"""
import os

from .api import create_app
from .keys import KeyStore
from .sectors import setup_b2b_sales
from .store import Store

DB_PATH = os.environ.get("ORDO_DB", "ordo.db")

store = Store(db_path=DB_PATH)
setup_b2b_sales(store)
app = create_app(store, KeyStore(DB_PATH))
