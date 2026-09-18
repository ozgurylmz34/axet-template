# -*- coding: utf-8 -*-
"""KD derleyici: yer tutucu kod bloklarını ekran görüntüleriyle değiştirir, görselleri kırpar, HTML/PDF üretir,
istenirse uygulama içi yardım kopyasını günceller.

İki girdi biçimi vardır; biri verilir, ikisi birden değil:
    A) elle yazılmış Markdown + eşleme dosyası
       python build_kd_pdf.py <KD.md> <KD.html> --map eslesme.json [--title "Başlık"] [--trim-from <ham_klasör>]
                              [--write-clean] [--help-dir <app>/webapp/help] [--pdf]
    B) makine üretimi manifest (Markdown elle yazılmaz)
       python build_kd_pdf.py <KD.html> --manifest kilavuz.json [--write-md <KD.md>] [--title ...]
                              [--trim-from <ham_klasör>] [--help-dir ...] [--pdf]

Eşleme dosyası:
    {
      "fences": {"<kod bloğunda geçen anahtar>": [{"img": "kd-01.png", "caption": "Şekil 1 — ..."}]},
      "after_heading": {"### 5.6 Başlık": [{"img": "kd-06.png", "caption": "Şekil 6 — ..."}]},
      "strip_circled_numbers": false
    }
  fences        : içinde anahtar geçen kod bloğunun TAMAMI görsel(ler)le değişir (kod bloğu içindeki ![]() ayrıştırılmaz).
  after_heading : görsel başlığın hemen altına bir kez eklenir; görsel zaten dokümanda varsa eklenmez.
  --trim-from   : ham görüntüler bu klasörden okunur, beyaz kenarı kırpılıp `<html klasörü>/screenshots/` altına yazılır (Pillow).
  --write-clean : dönüştürülmüş Markdown kaynağa geri yazılır (tekrar koşumda aynı sonucu verir).
  --help-dir    : HTML `kullanici-kilavuzu.html` adıyla, görseller `screenshots/` altına kopyalanır.

Manifest dosyası (biçim B, `--manifest`):
    {
      "title": "Sipariş Onay - Kullanıcı Kılavuzu",      // isteğe bağlı; --title verilirse o kazanır
      "intro": "Bu kılavuz ... anlatır.",          // isteğe bağlı giriş paragrafı
      "heading_level": 2,                          // isteğe bağlı, varsayılan 2
      "steps": [
        {"heading": "Liste ekranını açma", "text": "İşlem kodunu girin.",
         "img": "kd-01-liste.png", "caption": "Şekil 1 - Liste ekranı"}
      ]
    }
  · `steps` boş olamaz, her adımda `heading` zorunludur (yoksa çıkış 2 = şema hatası).
  · `text` yazılmamışsa adım **[AÇIKLAMA YAZILMADI]** olarak üretilir ve çıkış 1 olur. Araç adım
    metnini KENDİ UYDURMAZ: eksik açıklama sessizce geçilirse kılavuz "tamam" görünür ama boştur.
  · `text` liste de olabilir (her öğe ayrı paragraf).
  · `img` isteğe bağlıdır (yalnız metin taşıyan adım olabilir). Verilirse `--trim-from` ve eksik
    görsel denetimi biçim A ile aynı işler; `caption` yazılmazsa başlık kullanılır.
  · Görsel adları `capture_kd_screens.js` yapılandırmasındaki `{"do":"shot","name":...}` adlarıyla
    aynı yazılır — bu eşliği araç ÖLÇMEZ (iki dosya birbirinden bağımsız yazılır).

Çıkış: 0 başarılı · 1 eşleşmeyen anahtar / eksik görsel / PDF hatası · 2 eksik bağımlılık ya da okunamayan girdi.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_doc_pdf  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): build_kd_pdf — biçim A'da eşleme anahtar/başlıklarının dokümanda bulunması, biçim B'de "
         "manifest şemasının geçerliliği ve adım açıklamalarının YAZILMIŞ olması; her iki biçimde görsel "
         "dosyalarının varlığı ve HTML/PDF üretimi. Bakılmayanlar: görüntüdeki verinin temizliği, alt ekran "
         "kapsamı, içindekiler bağlantıları (→ verify_doc_html.py), metin içeriği, manifest görsel adlarının "
         "capture_kd_screens.js yapılandırmasıyla eşliği (ÖLÇÜLMEZ).")

PILLOW_INSTALL = "python -m pip install Pillow"
FENCE = re.compile(r"```([^\n]*)\n(.*?)\n```[^\n]*\n?", re.S)
CIRCLED = re.compile(r"[①-⑩]\s?")


def _figure_md(items):
    out = []
    for it in items:
        cap = it.get("caption", "")
        out.append("![%s](screenshots/%s)\n\n*%s*\n" % (cap, it["img"], cap))
    return "\n" + "\n".join(out) + "\n"


def apply_map(md, mapping):
    """Döner: (yeni_md, bulunamayan_anahtarlar, kullanılan_görseller)."""
    fences = mapping.get("fences", {}) or {}
    after = mapping.get("after_heading", {}) or {}
    used_keys, images = set(), []

    def _sub(m):
        lang, content = m.group(1).strip().lower(), m.group(2)
        if lang.startswith("mermaid"):
            return m.group(0)
        for key, items in fences.items():
            if key in content:
                used_keys.add(key)
                images.extend(it["img"] for it in items)
                return _figure_md(items)
        return m.group(0)

    md = FENCE.sub(_sub, md)
    missing = []
    for key, items in fences.items():
        if key in used_keys:
            continue
        # Tekrar koşum: blok daha önce değiştirildiyse görseller zaten dokümandadır → eksik sayılmaz.
        if items and all(("screenshots/%s)" % it["img"]) in md for it in items):
            images.extend(it["img"] for it in items)
            continue
        missing.append(key)

    lines = md.split("\n")
    for heading, items in after.items():
        idx = next((i for i, ln in enumerate(lines) if ln.strip() == heading.strip()), None)
        if idx is None:
            missing.append(heading)
            continue
        new_items = [it for it in items if ("screenshots/%s)" % it["img"]) not in md]
        images.extend(it["img"] for it in items)
        if new_items:
            lines[idx + 1:idx + 1] = _figure_md(new_items).split("\n")
            md = "\n".join(lines)
    md = "\n".join(lines)
    if mapping.get("strip_circled_numbers"):
        md = CIRCLED.sub("", md)
    return md, missing, images


ACIKLAMA_YOK = "**[AÇIKLAMA YAZILMADI]**"


class ManifestHatasi(ValueError):
    """Manifest şeması geçersiz (çıkış 2). Eksik açıklama şema hatası DEĞİLDİR — o bir bulgudur (çıkış 1)."""


def manifest_to_md(manifest):
    """Manifestten KD Markdown'ı üretir. Döner: (md, aciklamasi_eksik_basliklar, görseller).

    Şema ihlalinde ManifestHatasi yükselir. `text` eksikse metin yerine ACIKLAMA_YOK yazılır ve başlık
    eksik listesine düşer: araç adım açıklamasını uydurmaz, eksikliği GÖRÜNÜR kılar.
    """
    if not isinstance(manifest, dict):
        raise ManifestHatasi("manifest bir JSON nesnesi olmalı")
    steps = manifest.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ManifestHatasi("manifest: 'steps' boş olmayan bir liste olmalı")
    seviye = manifest.get("heading_level", 2)
    if not isinstance(seviye, int) or isinstance(seviye, bool) or not 1 <= seviye <= 6:
        raise ManifestHatasi("manifest: 'heading_level' 1-6 arası tam sayı olmalı (varsayılan 2)")

    parcalar, eksik, images = [], [], []
    baslik = manifest.get("title")
    if baslik:
        parcalar.append("# %s" % baslik)
    giris = manifest.get("intro")
    if giris:
        parcalar.append(str(giris).strip())

    for i, adim in enumerate(steps, 1):
        if not isinstance(adim, dict):
            raise ManifestHatasi("manifest: steps[%d] bir nesne olmalı" % i)
        h = adim.get("heading")
        if not isinstance(h, str) or not h.strip():
            raise ManifestHatasi("manifest: steps[%d] 'heading' zorunlu (boş olamaz)" % i)
        h = h.strip()
        parcalar.append("%s %s" % ("#" * seviye, h))
        metin = adim.get("text")
        if isinstance(metin, list):
            metin = "\n\n".join(str(x).strip() for x in metin if str(x).strip())
        if isinstance(metin, str) and metin.strip():
            parcalar.append(metin.strip())
        else:
            parcalar.append(ACIKLAMA_YOK)
            eksik.append(h)
        img = adim.get("img")
        if img is not None:
            if not isinstance(img, str) or not img.strip():
                raise ManifestHatasi("manifest: steps[%d] 'img' boş olmayan bir dosya adı olmalı" % i)
            images.append(img)
            parcalar.append(_figure_md([{"img": img, "caption": adim.get("caption") or h}]).strip())

    return "\n\n".join(parcalar) + "\n", eksik, images


def trim_image(src, dst, threshold=242, margin=14):
    """Beyaz kenarı kırpar (Pillow). Eksikse SystemExit(2)."""
    try:
        from PIL import Image
    except ImportError:
        print("HATA: Pillow yok; --trim-from kullanılamaz. Kurulum: " + PILLOW_INSTALL, file=sys.stderr)
        raise SystemExit(2)
    im = Image.open(src).convert("RGB")
    mask = im.convert("L").point(lambda p: 255 if p < threshold else 0)
    box = mask.getbbox()
    if box:
        l, t, r, b = box
        box = (max(0, l - margin), max(0, t - margin), min(im.width, r + margin), min(im.height, b + margin))
        im = im.crop(box)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst)
    return im.size


def main(argv):
    ap = argparse.ArgumentParser(description="KD Markdown (ya da adım manifesti) → görselli HTML/PDF")
    ap.add_argument("md", nargs="?", default=None, help="biçim A: elle yazılmış KD Markdown")
    ap.add_argument("html")
    ap.add_argument("--map", default=None, help="biçim A: eşleme dosyası (KD.md ile birlikte zorunlu)")
    ap.add_argument("--manifest", default=None, help="biçim B: adım manifesti (KD.md ve --map yerine)")
    ap.add_argument("--write-md", default=None, help="biçim B: üretilen Markdown'ı bu yola yaz")
    ap.add_argument("--title", default=None)
    ap.add_argument("--trim-from", default=None)
    ap.add_argument("--write-clean", action="store_true")
    ap.add_argument("--help-dir", default=None)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args(argv)
    print(SCOPE)

    # Girdi biçimi TEK olur: ikisi birlikte verilirse hangisinin kazandığı sessizce belirlenmez.
    if a.manifest and (a.md or a.map):
        print("HATA: --manifest ile birlikte KD.md ya da --map verilmez (biçim A ve B ayrıdır)", file=sys.stderr)
        return 2
    if not a.manifest and not (a.md and a.map):
        print("HATA: ya <KD.md> + --map (biçim A) ya da --manifest (biçim B) verilir", file=sys.stderr)
        return 2
    if a.write_md and not a.manifest:
        print("HATA: --write-md yalnız --manifest ile anlamlıdır (biçim A'da kaynak zaten dosyadır)", file=sys.stderr)
        return 2
    if a.write_clean and a.manifest:
        print("HATA: --write-clean biçim A içindir; manifest biçiminde --write-md kullanılır", file=sys.stderr)
        return 2

    try:
        if a.manifest:
            with open(a.manifest, encoding="utf-8-sig") as fh:
                manifest = json.load(fh)
        else:
            with open(a.md, encoding="utf-8") as fh:
                md = fh.read()
            with open(a.map, encoding="utf-8-sig") as fh:
                mapping = json.load(fh)
    except (OSError, ValueError) as exc:
        print("HATA: girdi okunamadı: %s" % exc, file=sys.stderr)
        return 2

    missing_text = []
    if a.manifest:
        try:
            md, missing_text, images = manifest_to_md(manifest)
        except ManifestHatasi as exc:
            print("HATA: %s" % exc, file=sys.stderr)
            return 2
        missing_keys = []
        if a.title is None:
            a.title = manifest.get("title")
    else:
        md, missing_keys, images = apply_map(md, mapping)
    shot_dir = os.path.join(os.path.dirname(os.path.abspath(a.html)), "screenshots")

    if a.trim_from:
        for img in dict.fromkeys(images):
            src = os.path.join(a.trim_from, img)
            if os.path.exists(src):
                w, h = trim_image(src, os.path.join(shot_dir, img))
                print("kırpıldı: %s (%dx%d)" % (img, w, h))

    missing_imgs = [img for img in dict.fromkeys(images) if not os.path.exists(os.path.join(shot_dir, img))]

    if a.write_clean:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("kaynak güncellendi:", a.md)
    if a.write_md:
        with open(a.write_md, "w", encoding="utf-8") as fh:
            fh.write(md)
        print("Markdown yazıldı:", a.write_md)

    counts = build_doc_pdf.render_html(md, a.html, a.title)
    print("OK | %s | <img>: %d | <figure>: %d | eşlemeden görsel: %d" % (a.html, counts["img"], counts["figure"],
                                                                        len(dict.fromkeys(images))))

    if a.help_dir:
        os.makedirs(os.path.join(a.help_dir, "screenshots"), exist_ok=True)
        shutil.copyfile(a.html, os.path.join(a.help_dir, "kullanici-kilavuzu.html"))
        copied = 0
        if os.path.isdir(shot_dir):
            for name in os.listdir(shot_dir):
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                    shutil.copyfile(os.path.join(shot_dir, name), os.path.join(a.help_dir, "screenshots", name))
                    copied += 1
        print("yardım kopyası: %s (%d görsel) — canlıda görünmesi yeniden deploy ister" % (a.help_dir, copied))

    rc = 0
    for k in missing_keys:
        print("BULGU: eşleme anahtarı dokümanda bulunamadı: %s" % k)
        rc = 1
    for h in missing_text:
        print("BULGU: manifest adımının açıklaması yazılmamış: %s" % h)
        rc = 1
    for img in missing_imgs:
        print("BULGU: görsel dosyası yok: screenshots/%s" % img)
        rc = 1
    if a.pdf:
        prc = build_doc_pdf.to_pdf(a.html)
        rc = prc if prc == 2 else (rc or prc)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
