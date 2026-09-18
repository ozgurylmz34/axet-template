# -*- coding: utf-8 -*-
"""Kilit politikası (aXet 2026-09-14) — model/araç kilit TEMİZLEMEZ; kendi kilidini her yolda bırakır;
çakışmada dürüstçe durur (SM12 tarifi). Süreç içi, SAHTE oturum (ağ yok).

Kapsam (ölçülen): statik tarama (üretim .py'lerinde kilit temizleme çağrısı / handle'sız UNLOCK yok) ·
`SAPADTClient.lock_object` 403 dalları + meşru `NO_LOCK_SUPPORT`/`IMPLICIT_LOCK` dönüşleri ·
`_handle_activation_403` · `unlock_object` dönüş dürüstlüğü · `SAPClient.push_object` kilit bırakma yolları ·
`atom._push_bdef_kaynak` PUT istisnasında UNLOCK.
Kapsam DIŞI (bakılmadı): gerçek SAP enqueue davranışı · süreç öldürülmesi (PATTERN #13; kodla önlenemez) ·
`lock_object_with_retry`/`object_lock` (üretimde çağıranı yok — IMPLEMENTATION.md §18 açık kalem).
GERÇEK gövdeler koşar; yalnız HTTP oturumu ve push'un bağımlı uçları sahtedir.
"""
from __future__ import annotations

import ast
import contextlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import _helpers as H

sys.dont_write_bytecode = True
LIB = H.SCRIPTS / "sapadt" / "lib"
for _p in (H.SCRIPTS, LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sapadt  # noqa: E402,F401  (lib yolunu hazırlar)
import sap_adt_lib as L  # noqa: E402
import sap_client as SC  # noqa: E402

KULLANICI = H.KULLANICI
TRANSPORT = "TESTK900001"
OBJ_URL = "/sap/bc/adt/oo/classes/zcl_ca000_kilit"
AD = "ZCA000_KILIT_PROG"
KAYNAK = "REPORT zca000_kilit_prog.\nWRITE 'x'.\n"

# ── statik tarama ────────────────────────────────────────────────────────────────────────────────
# Adlar parçalı yazılır ki bu dosyanın kendisi taramaya takılmasın (testler zaten tarama dışı).
YASAK_KILIT_CAGRILARI = frozenset({"clear_" + "enqueue_lock", "force_" + "unlock"})


def _sorgu_dizesi_ihlali(dize: str) -> bool:
    return "_action=UNLOCK" in dize and "lockHandle" not in dize


def kilit_ihlalleri(metin: str) -> list[str]:
    """Üretim kaynağında (1) kilit temizleme fonksiyonu tanımı/çağrısı (2) `lockHandle`'sız `_action=UNLOCK` sözlüğü
    (3) `lockHandle`'sız `_action=UNLOCK` içeren dize sabiti / f-string (URL sorgu dizesi yolu).

    Kapsam beyanı (3): yorumlar AST'de yoktur; ifade-deyimi olarak duran dizeler (docstring, belge satırı) atlanır.
    f-string'in sabit parçaları birleştirilip TEK dize olarak değerlendirilir. Bakılmayan: `"_action=" + "UNLOCK"`
    gibi parçalara bölünmüş sabitler, çalışma anında üretilen dizeler.
    """
    bulgular = []
    agac = ast.parse(metin)
    atla = set()   # docstring/belge satırı sabitleri ve f-string parçaları (f-string bütün olarak bakılır)
    for d in ast.walk(agac):
        if isinstance(d, ast.Expr) and isinstance(d.value, (ast.Constant, ast.JoinedStr)):
            atla.add(id(d.value))
            if isinstance(d.value, ast.JoinedStr):
                atla.update(id(p) for p in d.value.values)
        elif isinstance(d, ast.JoinedStr):
            atla.update(id(p) for p in d.values)
    for d in ast.walk(agac):
        if isinstance(d, ast.JoinedStr) and id(d) not in atla:
            sabit = "".join(p.value for p in d.values if isinstance(p, ast.Constant) and isinstance(p.value, str))
            if _sorgu_dizesi_ihlali(sabit):
                bulgular.append(f"{d.lineno}: handle'sız UNLOCK (f-string)")
        elif (isinstance(d, ast.Constant) and isinstance(d.value, str) and id(d) not in atla
              and _sorgu_dizesi_ihlali(d.value)):
            bulgular.append(f"{d.lineno}: handle'sız UNLOCK (dize)")
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name in YASAK_KILIT_CAGRILARI:
            bulgular.append(f"{d.lineno}: tanım {d.name}")
        elif isinstance(d, ast.Call):
            f = d.func
            ad = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if ad in YASAK_KILIT_CAGRILARI:
                bulgular.append(f"{d.lineno}: çağrı {ad}")
        elif isinstance(d, ast.Dict):
            anahtar = {k.value: v for k, v in zip(d.keys, d.values)
                       if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            act = anahtar.get("_action")
            if isinstance(act, ast.Constant) and act.value == "UNLOCK" and "lockHandle" not in anahtar:
                bulgular.append(f"{d.lineno}: handle'sız UNLOCK")
    return bulgular


def uretim_py():
    return [p for p in H.SKILLS_SAP.rglob("*.py")
            if "__pycache__" not in p.parts and "tests" not in p.parts]


# ── sahte HTTP ───────────────────────────────────────────────────────────────────────────────────
class _Y:
    def __init__(self, kod=200, metin="", headers=None):
        self.status_code, self.text, self.headers = kod, metin, headers or {}
        self.content = metin.encode("utf-8")


class _Oturum:
    verify = False

    def __init__(self, yonlendir):
        self.cagri: list[dict] = []
        self.yonlendir = yonlendir
        self.headers: dict = {}

    def _k(self, method, url, **kw):
        # URL sorgu dizesi de kaydedilir (`?_action=UNLOCK` yolu testlerden kaçmasın — gate L1/MU1);
        # açık `params` aynı anahtarı ezer (requests da ikisini birleştirir).
        params = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
        params.update(kw.get("params") or {})
        c = {"method": method.upper(), "url": url, "params": params}
        self.cagri.append(c)
        r = self.yonlendir(c)
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, **kw):
        return self._k("POST", url, **kw)

    def put(self, url, **kw):
        return self._k("PUT", url, **kw)

    def get(self, url, **kw):
        return self._k("GET", url, **kw)

    def delete(self, url, **kw):
        return self._k("DELETE", url, **kw)

    def request(self, method, url, **kw):
        return self._k(method, url, **kw)


class _LibAdt(L.SAPADTClient):
    def __init__(self, yonlendir):  # noqa: D401 — gerçek __init__ bağlantı arar
        self.url = "https://example.invalid:44300"
        self.session = _Oturum(yonlendir)
        self.csrf_token = "TOKEN"
        self.client = "100"
        self.language = "TR"
        self.user = KULLANICI
        self._auth_provider = None
        self.debug_enabled = False
        self.timeout_default = 5
        self.timeout_short = 5
        # gerçek __init__ (sap_adt_lib :1130-1140) ile aynı başlangıç değerleri
        self._last_lock_corrnr = None
        self._last_lock_is_link_up = None
        self._last_lock_effective_transport = None

    def _get_headers(self, *a, **k):
        return {}

    def fetch_csrf_token(self, force_refresh=False):
        return self.csrf_token

    def _update_cookies(self, response):
        return None


def _eylemler(adt, eylem):
    return [c for c in adt.session.cagri if c["params"].get("_action") == eylem]


# ── M1: gerçek lock_object + gerçek push_object, aynı süreçte önceki başarılı kilit ─────────────────
T_ONCEKI = "TESTK900222"   # aynı süreçte önceki objenin kilidinden kalan transport
T_SAP = "TESTK900333"      # meşru Bug-11: SAP'nin atadığı (istenenden farklı) istek
URL_ONCEKI = "/sap/bc/adt/programs/programs/zca000_onceki"


def _kilit_yonlendir(hedef):
    """Strateji 1-2 (locks/objectlock) 404; önceki obje 200 + CORRNR=T_ONCEKI; hedef objenin LOCK'u `hedef(c)`."""
    def y(c):
        if c["params"].get("_action") == "LOCK":
            if "/sap/bc/adt/locks" in c["url"] or "objectlock" in c["url"]:
                return _Y(404, "")
            if URL_ONCEKI in c["url"]:
                return _Y(200, f"<DATA><LOCK_HANDLE>HA</LOCK_HANDLE><CORRNR>{T_ONCEKI}</CORRNR>"
                               f"<IS_LINK_UP></IS_LINK_UP></DATA>")
            return hedef(c)
        return _Y(200, "")
    return y


class _GercekKilitAdt(_LibAdt):
    """lock_object/_verify_and_return_lock/unlock_object GERÇEK; push'un bağımlı uçları sahte; PUT kaydedilip durdurulur."""

    def __init__(self, yonlendir):
        super().__init__(yonlendir)
        self.put_kayit: list[tuple] = []

    def get_transport_info(self, url):
        return TRANSPORT

    def register_object_in_transport(self, *a, **k):
        return {"registered": True, "method": "sahte"}

    def fetch_source_etag(self, url):
        return None

    def _extract_modification_support(self, response):
        return ("", "absent")

    def set_object_source(self, url, src, lock, transport, etag=None):
        self.put_kayit.append((lock, transport))
        raise RuntimeError("sahte: PUT burada durduruldu")


@contextlib.contextmanager
def _sessiz_uyku():
    import time as _t
    eski, sayac = _t.sleep, []
    _t.sleep = lambda *a, **k: sayac.append(a)
    try:
        yield sayac
    finally:
        _t.sleep = eski


# ── push_object sahte istemcisi ──────────────────────────────────────────────────────────────────
class _PushAdt(L.SAPADTClient):
    def __init__(self, put_istisnasi=None, unlock_donus=True, kilit_bilgisi=None, kilit_istisnasi=None):
        self.url = "https://example.invalid:44300"
        self.session = _Oturum(lambda c: _Y(599, "beklenmeyen"))
        self.csrf_token = "TOKEN"
        self.user = KULLANICI
        self.debug_enabled = False
        self._last_lock_is_link_up = ""
        self._etkin = TRANSPORT
        self.put_istisnasi, self.unlock_donus = put_istisnasi, unlock_donus
        self.kilit_bilgisi, self.kilit_istisnasi = kilit_bilgisi, kilit_istisnasi
        self.kayit: list[tuple] = []

    @property
    def _last_lock_effective_transport(self):
        return self._etkin

    @_last_lock_effective_transport.setter
    def _last_lock_effective_transport(self, v):
        self._etkin = v

    def get_transport_info(self, url):
        return TRANSPORT

    def is_object_locked(self, url):
        self.kayit.append(("is_object_locked", url))
        return self.kilit_bilgisi

    def clear_enqueue_lock(self, *a, **k):   # ⛔ ÇAĞRILMAMALI — çağrılırsa kayda geçer
        self.kayit.append(("CLEAR", a))
        return True

    def register_object_in_transport(self, name, transport, object_type):
        return {"registered": True, "method": "sahte"}

    def fetch_source_etag(self, url):
        return None

    def lock_object(self, url, transport=None, **kw):
        self.kayit.append(("LOCK", url))
        if self.kilit_istisnasi:
            raise self.kilit_istisnasi
        return "LOCK1"

    def set_object_source(self, url, src, lock, transport, etag=None):
        self.kayit.append(("PUT", lock))
        if self.put_istisnasi:
            raise self.put_istisnasi
        return True

    def unlock_object(self, url, lock):
        self.kayit.append(("UNLOCK", lock))
        return self.unlock_donus

    def activate_object(self, name, url):
        self.kayit.append(("ACTIVATE", name))
        return {"success": True}

    def get_object_source(self, url, return_etag=False, version=None):
        return KAYNAK

    def adimlar(self, ad):
        return [k for k in self.kayit if k[0] == ad]


class _KilitSonrasiPatlayan(_PushAdt):
    """Kilit alındıktan SONRA, yüklemeden ÖNCE istisna: yalnız `finally` bırakabilir."""

    @property
    def _last_lock_effective_transport(self):
        if any(k[0] == "LOCK" for k in self.kayit):
            raise RuntimeError("sahte: kilit sonrası istisna")
        return TRANSPORT

    @_last_lock_effective_transport.setter
    def _last_lock_effective_transport(self, v):
        pass


class KilitPolitikasi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_kilit_"))
        cls.dosya = cls.root / f"{AD}.prog.abap"
        cls.dosya.write_text(KAYNAK, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"KİLİT {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── T0 statik ────────────────────────────────────────────────────────────────────────────────
    def test_T0_statik_kilit_temizleme_yok(self):
        # tarayıcının kendisi çalışıyor mu (pozitif/negatif kontrol)
        self.assertTrue(kilit_ihlalleri("c." + "clear_" + "enqueue_lock(u)\n"))
        self.assertTrue(kilit_ihlalleri("def " + "force_" + "unlock(x):\n    pass\n"))
        self.assertTrue(kilit_ihlalleri("s.post(u, params={'_action': 'UNLOCK', 'accessMode': 'MODIFY'})\n"))
        self.assertFalse(kilit_ihlalleri("s.post(u, params={'_action': 'UNLOCK', 'lockHandle': h})\n"))
        self.assertFalse(kilit_ihlalleri("s.post(u, params={'_action': 'LOCK', 'accessMode': 'MODIFY'})\n"))
        # URL sorgu dizesiyle gönderilen handle'sız UNLOCK (gate L1 / MU1) — f-string ve düz birleştirme
        self.assertTrue(kilit_ihlalleri('s.post(f"{u}{o}?_action=UNLOCK&accessMode=MODIFY")\n'))
        self.assertTrue(kilit_ihlalleri('s.post(u + "?_action=UNLOCK")\n'))
        self.assertFalse(kilit_ihlalleri('s.post(f"{u}?_action=UNLOCK&lockHandle={h}")\n'))
        # negatif kontrol: belge dizesi ve yorum satırı bulgu DEĞİLDİR
        self.assertFalse(kilit_ihlalleri('"""modül: POST ?_action=UNLOCK"""\n'))
        self.assertFalse(kilit_ihlalleri('def f():\n    """POST to object URL with _action=UNLOCK"""\n    return 1\n'))
        self.assertFalse(kilit_ihlalleri("x = 1  # handle'sız ?_action=UNLOCK yorum satırı\n"))
        ihlal = []
        dosyalar = uretim_py()
        for p in dosyalar:
            for b in kilit_ihlalleri(p.read_text(encoding="utf-8", errors="replace")):
                ihlal.append(f"{p.relative_to(H.SKILLS_SAP).as_posix()}:{b}")
        self.kaydet("T0 üretim .py: kilit temizleme çağrısı/tanımı + handle'sız UNLOCK",
                    "0 bulgu", f"{len(dosyalar)} dosya, {len(ihlal)} bulgu: {ihlal[:4]}", not ihlal and len(dosyalar) > 20)

    def test_T0k_oturum_url_sorgusunu_kaydeder(self):
        """Sahte oturum URL sorgu dizesindeki `_action`'ı da görür (yoksa `?_action=UNLOCK` testlerden kaçar — gate L1)."""
        o = _Oturum(lambda c: _Y(200, ""))
        o.post("https://example.invalid/sap/bc/adt/oo/classes/z?_action=UNLOCK&accessMode=MODIFY")
        o.post("https://example.invalid/sap/bc/adt/oo/classes/z", params={"_action": "LOCK"})
        eylem = [c["params"].get("_action") for c in o.cagri]
        self.kaydet("T0k sahte oturum URL sorgusundaki _action'ı kaydeder", "['UNLOCK', 'LOCK']", eylem,
                    eylem == ["UNLOCK", "LOCK"])

    # ── L1 lock_object 403 dalları + meşru sentinel'ler ──────────────────────────────────────────
    def _kilit(self, yonlendir):
        adt = _LibAdt(yonlendir)
        tampon = io.StringIO()
        with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
            try:
                return adt, adt.lock_object(OBJ_URL, transport=TRANSPORT), None, tampon.getvalue()
            except Exception as exc:  # noqa: BLE001
                return adt, None, exc, tampon.getvalue()

    def test_L1_ayni_kullanici_403_durur_temizlemez(self):
        govde = f"<message>User {KULLANICI} is already editing object ZCL_CA000_KILIT</message>"
        adt, donus, exc, _log = self._kilit(
            lambda c: _Y(403, govde) if c["params"].get("_action") == "LOCK" else _Y(200, ""))
        ok = (isinstance(exc, L.SAPLockError) and getattr(exc, "lock_owner", None) == KULLANICI
              and "SM12" in str(exc) and not _eylemler(adt, "UNLOCK") and len(_eylemler(adt, "LOCK")) == 1
              and donus is None)
        self.kaydet("L1 aynı kullanıcı 403 → SAPLockError, UNLOCK/relock YOK, kilitsiz devam YOK",
                    "SAPLockError · LOCK 1 · UNLOCK 0",
                    f"exc={type(exc).__name__ if exc else None} donus={donus} lock={len(_eylemler(adt, 'LOCK'))} "
                    f"unlock={len(_eylemler(adt, 'UNLOCK'))}", ok)

    def test_L1k_baska_kullanici_403_kontrol(self):
        govde = "<message>User BASKA_KULLANICI is already editing object ZCL_CA000_KILIT</message>"
        adt, donus, exc, _log = self._kilit(lambda c: _Y(403, govde))
        ok = (isinstance(exc, L.SAPLockError) and exc.lock_owner == "BASKA_KULLANICI"
              and not _eylemler(adt, "UNLOCK") and len(_eylemler(adt, "LOCK")) == 1)
        self.kaydet("L1k KONTROL başka kullanıcı 403 → SAPLockError (değişmedi)", "SAPLockError · UNLOCK 0",
                    f"exc={type(exc).__name__ if exc else None} owner={getattr(exc, 'lock_owner', None)}", ok)

    def test_L1n_hepsi_404_no_lock_support_korunur(self):
        adt, donus, exc, _log = self._kilit(lambda c: _Y(404, ""))
        ok = exc is None and donus == "NO_LOCK_SUPPORT" and adt._last_lock_no_support_reason == "ENDPOINT_ABSENT_404"
        self.kaydet("L1n KONTROL tüm stratejiler 404 → NO_LOCK_SUPPORT (meşru dal korunur)", "NO_LOCK_SUPPORT",
                    f"donus={donus} exc={exc!r}", ok)

    def test_L1i_handlesiz_200_implicit_lock_korunur(self):
        adt, donus, exc, _log = self._kilit(lambda c: _Y(200, "<ok/>"))
        ok = exc is None and donus == "IMPLICIT_LOCK" and not _eylemler(adt, "UNLOCK")
        self.kaydet("L1i KONTROL 200 + handle yok → IMPLICIT_LOCK (meşru dal korunur)", "IMPLICIT_LOCK",
                    f"donus={donus} exc={exc!r}", ok)

    # ── L2 aktivasyon 403 ────────────────────────────────────────────────────────────────────────
    def _akt403(self, sahip):
        adt = _LibAdt(lambda c: _Y(403, "tekrar 403"))
        govde = (f'<exc:exception><properties><entry key="T100KEY-V1">{sahip}</entry></properties>'
                 f"<message>Kullanıcı {sahip} zaten ZCL_CA000_KILIT öğesini düzenliyor</message></exc:exception>")
        tampon = io.StringIO()
        with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
            r = adt._handle_activation_403(_Y(403, govde), "ZCL_CA000_KILIT", OBJ_URL, "<b/>", {})
        return adt, r

    def test_L2_aktivasyon_403_ayni_kullanici_temizleme_ve_retry_yok(self):
        adt, r = self._akt403(KULLANICI)
        mesaj = (r.get("errors") or [{}])[0].get("message", "")
        ok = (r.get("success") is False and not adt.session.cagri and "SM12" in mesaj and KULLANICI in mesaj
              and "otomatik" in mesaj.lower())
        self.kaydet("L2 aktivasyon 403 aynı kullanıcı → HTTP çağrısı 0 (LOCK/UNLOCK/retry yok) + SM12",
                    "success False · çağrı 0", f"cagri={[(c['method'], c['params']) for c in adt.session.cagri][:3]} "
                                               f"mesaj={mesaj[:70]}", ok)

    def test_L2k_aktivasyon_403_baska_kullanici_kontrol(self):
        adt, r = self._akt403("BASKA_KULLANICI")
        mesaj = (r.get("errors") or [{}])[0].get("message", "")
        ok = r.get("success") is False and not adt.session.cagri and "BASKA_KULLANICI" in mesaj
        self.kaydet("L2k KONTROL aktivasyon 403 başka kullanıcı → çağrı 0", "success False · çağrı 0",
                    f"cagri={len(adt.session.cagri)} mesaj={mesaj[:70]}", ok)

    # ── L3 unlock_object dönüşü ──────────────────────────────────────────────────────────────────
    def test_L3_unlock_hepsi_duserse_false(self):
        adt = _LibAdt(lambda c: _Y(500, "iç hata"))
        r = adt.unlock_object(OBJ_URL, "H1")
        ok = r is False and all(c["params"].get("lockHandle") for c in adt.session.cagri)
        self.kaydet("L3 unlock tüm stratejiler 500 → False (eskisi True)", "False",
                    f"donus={r} cagri={len(adt.session.cagri)}", ok)

    def test_L3k_unlock_basarili_true_kontrol(self):
        adt = _LibAdt(lambda c: _Y(200, ""))
        r = adt.unlock_object(OBJ_URL, "H1")
        r2 = adt.unlock_object(OBJ_URL, "NO_LOCK_SUPPORT")
        ok = r is True and r2 is True and len(adt.session.cagri) == 1
        self.kaydet("L3k KONTROL unlock 200 → True · NO_LOCK_SUPPORT → istek yok", "True · çağrı 1",
                    f"{r} {r2} cagri={len(adt.session.cagri)}", ok)

    # ── S push_object ────────────────────────────────────────────────────────────────────────────
    def _push(self, adt):
        ist = object.__new__(SC.SAPClient)
        ist.adt_client = adt
        ist.debug_enabled = False
        ist.local_base = self.root
        ist._find_existing_transport = lambda name, otype, transport: transport
        tampon = io.StringIO()
        with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
            r = ist.push_object(AD, object_type="prog", transport=TRANSPORT, source_file=str(self.dosya))
        return r, tampon.getvalue()

    def test_S1_put_istisnasi_tek_unlock_ayni_handle(self):
        adt = _PushAdt(put_istisnasi=RuntimeError("sahte: bağlantı koptu"))
        r, _log = self._push(adt)
        ok = (r.get("success") is False and r.get("error_type") == "RuntimeError"
              and adt.adimlar("UNLOCK") == [("UNLOCK", "LOCK1")] and not adt.adimlar("CLEAR")
              and r.get("lock_released") is True)
        self.kaydet("S1 PUT istisnası → UNLOCK tam 1 kez (LOCK1), temizleme yok", "UNLOCK [LOCK1] · CLEAR 0",
                    f"unlock={adt.adimlar('UNLOCK')} clear={len(adt.adimlar('CLEAR'))} released={r.get('lock_released')}", ok)

    def test_S2_kendi_kilidi_gorunse_de_temizleme_yok(self):
        adt = _PushAdt(kilit_bilgisi={"locked": True, "lock_owner": KULLANICI, "lock_handle": None})
        r, _log = self._push(adt)
        ok = r.get("success") is True and not adt.adimlar("CLEAR") and adt.adimlar("UNLOCK") == [("UNLOCK", "LOCK1")]
        self.kaydet("S2 kilit sondası 'kendi kilidi' dese de clear çağrısı YOK", "CLEAR 0 · success",
                    f"clear={len(adt.adimlar('CLEAR'))} success={r.get('success')} unlock={adt.adimlar('UNLOCK')}", ok)

    def test_S3_kilit_sonrasi_istisna_finally_birakir(self):
        adt = _KilitSonrasiPatlayan()
        r, _log = self._push(adt)
        ok = (r.get("success") is False and not adt.adimlar("PUT")
              and adt.adimlar("UNLOCK") == [("UNLOCK", "LOCK1")])
        self.kaydet("S3 kilit sonrası/yükleme öncesi istisna → finally UNLOCK 1", "UNLOCK [LOCK1] · PUT 0",
                    f"err={r.get('error_type')} unlock={adt.adimlar('UNLOCK')} put={len(adt.adimlar('PUT'))}", ok)

    def test_S4_unlock_false_lock_released_false(self):
        adt = _PushAdt(unlock_donus=False)
        r, log = self._push(adt)
        ok = r.get("lock_released") is False and "SM12" in log and len(adt.adimlar("UNLOCK")) >= 2
        self.kaydet("S4 unlock False dönerse lock_released False + SM12 uyarısı", "lock_released False",
                    f"released={r.get('lock_released')} unlock={len(adt.adimlar('UNLOCK'))}", ok)

    def test_S5_kilit_cakismasi_durust_mesaj(self):
        adt = _PushAdt(kilit_istisnasi=L.SAPLockError(
            f"Obje zaten {KULLANICI} kullanıcısıyla kilitli", lock_owner=KULLANICI, status_code=403))
        r, log = self._push(adt)
        ok = (r.get("error_type") == "SAPLockError" and r.get("source_uploaded") is False
              and not adt.adimlar("PUT") and not adt.adimlar("UNLOCK") and not adt.adimlar("CLEAR")
              and "uploaded successfully" not in log and "SM12" in log)
        self.kaydet("S5 aynı kullanıcı kilit çakışması → PUT/UNLOCK/CLEAR yok, 'yüklendi' yalanı yok, SM12",
                    "SAPLockError · PUT 0", f"err={r.get('error_type')} up={r.get('source_uploaded')} "
                                            f"yalan={'VAR' if 'uploaded successfully' in log else 'YOK'}", ok)

    def test_S6_put_istisnasi_unlock_false_handle_tutulur(self):
        """Hata dalında UNLOCK False → handle None'a ÇEKİLMEZ, finally tekrar dener, lock_released False (gate M2 / MU8)."""
        adt = _PushAdt(put_istisnasi=RuntimeError("sahte: bağlantı koptu"), unlock_donus=False)
        r, log = self._push(adt)
        unlock = adt.adimlar("UNLOCK")
        ok = (r.get("success") is False and r.get("lock_released") is False and len(unlock) >= 2
              and all(h == "LOCK1" for _, h in unlock) and "SM12" in log)
        self.kaydet("S6 PUT istisnası + UNLOCK False → handle tutulur, finally tekrar dener, lock_released False",
                    "lock_released False · UNLOCK ≥2", f"released={r.get('lock_released')} unlock={unlock}", ok)

    # ── M1 Bug-11 otomatik ikinci kilit: yalnız sahipsiz 409 (CORRNR uyuşmazlığı) ───────────────────
    def _push_gercek(self, hedef, onceki_kilit=True):
        adt = _GercekKilitAdt(_kilit_yonlendir(hedef))
        tampon = io.StringIO()
        with _sessiz_uyku(), contextlib.redirect_stdout(tampon):
            if onceki_kilit:
                h = adt.lock_object(URL_ONCEKI, transport=T_ONCEKI)
                adt.unlock_object(URL_ONCEKI, h)
            adt.session.cagri.clear()
            ist = object.__new__(SC.SAPClient)
            ist.adt_client = adt
            ist.debug_enabled = False
            ist.local_base = self.root
            ist._find_existing_transport = lambda name, otype, transport: transport
            r = ist.push_object(AD, object_type="prog", transport=TRANSPORT, source_file=str(self.dosya))
        kilit_corrnr = [c["params"].get("corrNr") for c in _eylemler(adt, "LOCK")]
        return adt, r, tampon.getvalue(), kilit_corrnr

    def test_M1a_ayni_kullanici_403_bayat_transportla_ikinci_kilit_yok(self):
        govde = f"<message>User {KULLANICI} is already editing object {AD}</message>"
        adt, r, log, kilit = self._push_gercek(lambda c: _Y(403, govde))
        ok = (r.get("error_type") == "SAPLockError" and T_ONCEKI not in kilit and set(kilit) == {TRANSPORT}
              and "KABUL EDİLMEDİ" not in log and "Bug 11" not in log and "[KİLİT]" in log
              and adt._last_lock_effective_transport is None and not adt.put_kayit)
        self.kaydet("M1a önceki kilit + aynı kullanıcı 403 → ikinci LOCK yok, bayat corrNr yok, sahte transport uyarısı yok",
                    f"LOCK corrNr yalnız {TRANSPORT} · uyarı yok",
                    f"err={r.get('error_type')} lock_corrnr={kilit} etkin={adt._last_lock_effective_transport} "
                    f"uyari={'VAR' if 'KABUL EDİLMEDİ' in log else 'YOK'}", ok)

    def test_M1b_baska_kullanici_403_bayat_transportla_ikinci_kilit_yok(self):
        govde = f"<message>User BASKA_KULLANICI is already editing object {AD}</message>"
        adt, r, log, kilit = self._push_gercek(lambda c: _Y(403, govde))
        ok = (r.get("error_type") == "SAPLockError" and T_ONCEKI not in kilit and set(kilit) == {TRANSPORT}
              and "KABUL EDİLMEDİ" not in log and "BASKA_KULLANICI" in log and not adt.put_kayit)
        self.kaydet("M1b önceki kilit + başka kullanıcı 403 → ikinci LOCK yok, 'aynı kullanıcı' uyarısı yok",
                    f"LOCK corrNr yalnız {TRANSPORT}",
                    f"err={r.get('error_type')} lock_corrnr={kilit} "
                    f"uyari={'VAR' if 'KABUL EDİLMEDİ' in log else 'YOK'}", ok)

    def test_M1e_push_sozlesmesi_403_bayat_alanla_ikinci_kilit_yok(self):
        """push_object'in KENDİ sözleşmesi (lib sıfırlamasından bağımsız): kilit 403 + sahip ile düşer ve etkin-transport
        alanı bayat kalmışsa (sıfırlamayan bir kilit uygulaması) ikinci kilit YİNE denenmez."""
        adt = _PushAdt(kilit_istisnasi=L.SAPLockError(
            f"Obje zaten {KULLANICI} kullanıcısıyla kilitli", lock_owner=KULLANICI, status_code=403))
        adt._etkin = T_ONCEKI   # sahte lock_object alanı sıfırlamaz → bayat değer
        r, log = self._push(adt)
        ok = (r.get("error_type") == "SAPLockError" and len(adt.adimlar("LOCK")) == 1
              and "KABUL EDİLMEDİ" not in log and not adt.adimlar("PUT"))
        self.kaydet("M1e push sözleşmesi: 403+sahip ve bayat etkin transport → LOCK tam 1, Bug-11 uyarısı yok",
                    "LOCK 1", f"lock={len(adt.adimlar('LOCK'))} uyari={'VAR' if 'KABUL EDİLMEDİ' in log else 'YOK'}", ok)

    def test_M1c_http_409_onceki_transport_kullanilmaz(self):
        adt, r, log, kilit = self._push_gercek(
            lambda c: _Y(409, "<message>Object locked in transport TESTK900444</message>"))
        ok = (r.get("error_type") == "SAPLockError" and T_ONCEKI not in kilit and "KABUL EDİLMEDİ" not in log
              and not adt.put_kayit)
        self.kaydet("M1c önceki kilit + HTTP 409 (sahipsiz) → bayat transportla ikinci LOCK yok (alan sıfırlama)",
                    "LOCK corrNr'da T_ONCEKI yok", f"err={r.get('error_type')} lock_corrnr={kilit}", ok)

    def test_M1d_hepsi_404_put_bayat_transport_kullanmaz(self):
        adt, r, log, kilit = self._push_gercek(lambda c: _Y(404, ""))
        ok = adt.put_kayit == [("NO_LOCK_SUPPORT", TRANSPORT)]
        self.kaydet("M1d önceki kilit + tüm stratejiler 404 → PUT istenen transportla (önceki objeninkiyle değil)",
                    f"PUT [('NO_LOCK_SUPPORT', '{TRANSPORT}')]", f"put={adt.put_kayit}", ok)

    def test_H1_kilit_cakismasi_bilinen_hata_ipucu_k09(self):
        """Düz push yanıtında üst seviye `error` yok → `known_errors_hint` yalnız `client_log` metnine bakabilir.
        Kilit mesajı artık "EU 510" demediği için (L4) ipucu tarif metninden K-09'a düşmeli; aynı ve başka kullanıcı."""
        from sapadt import hints
        bolum = {}
        for sahip in (KULLANICI, "BASKA_KULLANICI"):
            govde = f"<message>User {sahip} is already editing object {AD}</message>"
            _adt, r, log, _k = self._push_gercek(lambda c, g=govde: _Y(403, g), onceki_kilit=False)
            resp = {"ok": False, "name": AD, "type": "prog", "result": r, "client_log": log}
            h = hints.known_errors_hint("adt_push_source", resp, None, 1) or {}
            bolum[sahip] = [x.get("section") for x in h.get("refs", [])]
        ok = all(any("K-09" in (b or "") for b in v) for v in bolum.values())
        self.kaydet("H1 push kilit çakışması (aynı/başka kullanıcı) → known_errors_hint K-09", "K-09 her ikisinde",
                    bolum, ok)

    def test_M1k_mesru_bug11_corrnr_uyusmazligi_kontrol(self):
        """KONTROL: sahipsiz 409 (aynı kullanıcı, CORRNR uyuşmazlığı) → Bug-11 SAP'nin atadığı istekle 1 kez yeniden kilitler."""
        def hedef(c):
            handle = "HB" if c["params"].get("corrNr") == T_SAP else "HX"
            return _Y(200, f"<DATA><LOCK_HANDLE>{handle}</LOCK_HANDLE><CORRNR>{T_SAP}</CORRNR>"
                           f"<IS_LINK_UP></IS_LINK_UP></DATA>")
        adt, r, log, kilit = self._push_gercek(hedef)
        nesne_kilit = [c["params"].get("corrNr") for c in _eylemler(adt, "LOCK")
                       if "/sap/bc/adt/locks" not in c["url"] and "objectlock" not in c["url"]]
        unlock_handlesiz = [c for c in _eylemler(adt, "UNLOCK") if not c["params"].get("lockHandle")]
        ok = (nesne_kilit == [TRANSPORT, T_SAP] and adt.put_kayit == [("HB", T_SAP)]
              and "KABUL EDİLMEDİ" in log and not unlock_handlesiz)
        self.kaydet("M1k KONTROL meşru Bug-11 (409 sahipsiz, CORRNR farklı) → 2. LOCK SAP'nin isteğiyle, PUT onunla",
                    f"LOCK [{TRANSPORT}, {T_SAP}] · PUT HB/{T_SAP}",
                    f"lock={nesne_kilit} put={adt.put_kayit} uyari={'VAR' if 'KABUL EDİLMEDİ' in log else 'YOK'}", ok)

    # ── A1 atom BDEF ─────────────────────────────────────────────────────────────────────────────
    def test_A1_bdef_put_istisnasi_unlock_ayni_handle(self):
        from sapadt.tools import atom

        class _BdefAdt:
            url, client, language = "https://example.invalid:44300", "100", "TR"

            def __init__(self):
                self.cagri = []

            def _request_with_csrf_retry(self, method, url, headers=None, params=None, data=None, **kw):
                self.cagri.append((method.upper(), dict(params or {})))
                act = (params or {}).get("_action")
                if act == "LOCK":
                    return _Y(200, "<LOCK_HANDLE>HB1</LOCK_HANDLE>")
                if method.lower() == "put":
                    raise RuntimeError("sahte: PUT sırasında bağlantı koptu")
                return _Y(200, "")

        adt = _BdefAdt()
        with self.assertRaises(RuntimeError):
            atom._push_bdef_kaynak(adt, "ZCA000_R_KILIT", "managed;", TRANSPORT)
        unlock = [p for m, p in adt.cagri if p.get("_action") == "UNLOCK"]
        ok = unlock == [{"_action": "UNLOCK", "lockHandle": "HB1"}]
        self.kaydet("A1 atom BDEF PUT istisnası → UNLOCK 1 (HB1)", "UNLOCK [HB1]", f"{adt.cagri}", ok)


if __name__ == "__main__":
    unittest.main()
