#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ui5_freestyle_traps — XML yorumu (`<!-- … -->`) T2/T3/T4 bulgusu üretmez; yorumun DIŞI körleşmez.

Davranış zaten vardı (`_ui5scan.xml_yorumsuz`: yorum aynı sayıda satır sonuyla değiştirilir ⇒ satır numarası ham
dosyayla aynı; kapanmamış `<!--` maskelenmez ⇒ uyarı KALIR, fail-closed). Bu dosya kaynak çekirdekteki
`ui5_xml_yorumu` vaka kümesinin aXet karşılığıdır:
  N* yorumdaki desen → temiz · K* gerçek ihlal → bulgu + DOĞRU satır · E* yorumla aynı satırdaki / yorumdan
  sonraki gerçek ihlal → bulgu · U1 kapanmamış yorum → uyarı kalır · 3. bağlam: fragment + `form:` öneki + CRLF.
KAPSAM — bakılmayan: JS yorumları (ayrı ayıklayıcı) · CDATA · işleme talimatı.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

S = "check_ui5_freestyle_traps.py"

VIEW_BAS = ('<mvc:View controllerName="zdemo.controller.Main"\n'
            '    xmlns:mvc="sap.ui.core.mvc" xmlns="sap.m"\n'
            '    xmlns:f="sap.ui.layout.form" xmlns:core="sap.ui.core">\n'
            '    <Page title="Demo">\n'
            '        <content>\n')
VIEW_SON = '        </content>\n    </Page>\n</mvc:View>\n'
FORM_BAS = ('            <f:Form editable="true">\n'
            '                <f:layout><f:ColumnLayout/></f:layout>\n'
            '                <f:formContainers><f:FormContainer><f:formElements>\n')
FORM_SON = '                </f:formElements></f:FormContainer></f:formContainers>\n            </f:Form>\n'
GECERLI = ('                    <f:FormElement label="A">\n'
           '                        <f:fields><Input value="{A}"/></f:fields>\n'
           '                    </f:FormElement>\n')
FRAG_BAS = ('<core:FragmentDefinition xmlns="sap.m" xmlns:core="sap.ui.core"\n'
            '    xmlns:form="sap.ui.layout.form">\n'
            '    <Dialog title="Demo">\n')
FRAG_SON = '    </Dialog>\n</core:FragmentDefinition>\n'
FRAG_FORM = ('        <form:Form><form:formContainers><form:FormContainer><form:formElements>\n'
             '            <form:FormElement label="C"><form:fields>{ICERIK}</form:fields></form:FormElement>\n'
             '        </form:formElements></form:FormContainer></form:formContainers></form:Form>\n')


def view(govde: str) -> str:
    return VIEW_BAS + govde + VIEW_SON


def form(elemanlar: str) -> str:
    return FORM_BAS + elemanlar + FORM_SON


def satir(metin: str, isaret: str) -> int:
    return metin.count("\n", 0, metin.index(isaret)) + 1


class TestXmlYorumu(unittest.TestCase):
    def _kos(self, ad, metin, beklenen, tur="view", eol="\n"):
        """beklenen: [(tuzak, işaret)] — satır no işaretin metindeki satırından."""
        kok = Path(tempfile.mkdtemp(prefix="ui5yorum_"))
        try:
            web = kok / "app" / "webapp"
            d, dosya = ((web / "view" / "fragments", "Demo.fragment.xml") if tur == "fragment"
                        else (web / "view", "Main.view.xml"))
            d.mkdir(parents=True)
            (d / dosya).write_bytes(metin.replace("\n", eol).encode("utf-8"))  # bayt: CRLF ekseni korunur
            rc, out = H.kos(S, kok / "app")
        finally:
            shutil.rmtree(kok, ignore_errors=True)
        bulgular = sorted((ln.split("  ")[1].split()[0], int(ln.split("  ")[0].rsplit(":", 1)[1]))
                          for ln in out.splitlines() if ln.startswith(("[İHLAL]", "[UYARI]")))
        istenen = sorted((t, satir(metin, i)) for t, i in beklenen)
        ok = bulgular == istenen and "KAPSAM: 1 " in out
        H.kaydet(ad, str(istenen)[:22], str(bulgular), ok)
        self.assertTrue(ok, f"{ad}: beklenen={istenen} gerçek={bulgular}\n{out}")

    # ── yorumdaki desen → bulgu YOK ──
    def test_N0_yorumsuz_cerceve_temiz(self):
        self._kos("xml: form-dışı VBox + geçerli f:fields → temiz", view(
            '            <VBox>\n' + form(GECERLI) + '            </VBox>\n'), [])

    def test_N4a_yorumdaki_fields_formdisi_vbox(self):
        self._kos("xml: yorumdaki `<f:fields>` + form-dışı VBox → T4 YOK", view(
            '            <!-- not: <f:fields> icine yalniz kontrol koyun -->\n'
            '            <VBox>\n' + form(GECERLI) + '            </VBox>\n'), [])

    def test_N4b_cok_satirli_olu_ornek(self):
        self._kos("xml: çok satırlı yorumda ölü `<f:fields><HBox>` → temiz", view(
            '            <!--\n'
            '                YANLIS ORNEK:\n'
            '                <f:fields><HBox><Input/><Button/></HBox></f:fields>\n'
            '            -->\n' + form(GECERLI)), [])

    def test_N2_yorumdaki_number(self):
        self._kos("xml: yorumdaki type=Number (tek + çok satır) → T2 YOK", view(
            '            <!-- eski: <Input type="Number" value="{Q}"/> -->\n'
            '            <!--\n'
            '                <Input type="Number" value="{Q}"/>\n'
            '            -->\n'
            '            <Input type="Text" value="{Q}"/>\n'), [])

    def test_N3_yorumdaki_core_title(self):
        self._kos("xml: yorumdaki `<core:Title` → T3 YOK", view(
            '            <!-- <core:Title text="Eski"/> -->\n'
            '            <Title text="Baslik"/>\n'), [])

    # ── gerçek ihlal → bulgu + doğru satır (körleşme yok) ──
    def test_K4_gercek_ihlal(self):
        self._kos("xml: gerçek `<f:fields><HBox>` → T4", view(form(
            '                    <f:FormElement label="B">\n'
            '                        <f:fields><HBox id="K4"><Input/></HBox></f:fields>\n'
            '                    </f:FormElement>\n')), [("T4", "<f:fields><HBox")])

    def test_K4b_cok_satirli_yorumdan_sonra_satir_no(self):
        metin = view('            <!--\n                satir 1\n                satir 2\n            -->\n' + form(
            '                    <f:FormElement label="B">\n'
            '                        <f:fields>\n'
            '                            <VBox id="K4b"><Input/></VBox>\n'
            '                        </f:fields>\n'
            '                    </f:FormElement>\n'))
        # T4 bulgusu kapsayıcının (`<VBox`) satırını basar
        self._kos("xml: çok satırlı yorumdan sonra T4, satır no DOĞRU", metin, [("T4", '<VBox id="K4b"')])

    def test_E1_yorumla_ayni_satirda_gercek_ihlal(self):
        self._kos("xml: yorum kapandıktan sonra aynı satırda type=Number → T2", view(
            '            <!-- not --> <Input type="Number" value="{Q}"/>\n'), [("T2", "<!-- not -->")])

    def test_U1_kapanmamis_yorum_fail_closed(self):
        self._kos("xml: kapanmamış `<!--` maskelenmez → T2 uyarısı KALIR", view(
            '            <!-- kapanmayan yorum\n'
            '            <Input type="Number" value="{Q}"/>\n'), [("T2", '<Input type="Number"')])

    # ── 3. bağlam: fragment + `form:` öneki + CRLF ──
    def test_N4c_fragment_crlf_yorum(self):
        self._kos("xml: fragment+form:+CRLF, yorumdaki örnek → temiz",
                  FRAG_BAS + '        <!-- ornek: <form:fields><FlexBox/></form:fields> -->\n'
                  '        <FlexBox>\n' + FRAG_FORM.replace("{ICERIK}", "<Input/>") + '        </FlexBox>\n' + FRAG_SON,
                  [], tur="fragment", eol="\r\n")

    def test_K4c_fragment_crlf_gercek_ihlal(self):
        metin = (FRAG_BAS + '        <!--\n uzun not\n -->\n'
                 + FRAG_FORM.replace("{ICERIK}", '<FlexBox id="K4c"/>') + FRAG_SON)
        self._kos("xml: fragment+CRLF, yorumdan sonra gerçek T4, satır DOĞRU", metin,
                  [("T4", "<form:fields><FlexBox")], tur="fragment", eol="\r\n")


if __name__ == "__main__":
    unittest.main()
