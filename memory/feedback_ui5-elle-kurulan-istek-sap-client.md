---
name: ui5-elle-kurulan-istek-sap-client
description: UI5'te manifest dışı kurulan istek (new ODataModel, ham fetch/XHR, sServiceUrl + URL) sap-client taşımaz - iki client aynı tarayıcıda açıkken hatasız çapraz-client okuma/yazma; ana modelin aUrlParams'ını devret, ayırıcı veriyle ölç
type: feedback
---

UI5'te `sap-client`'ı manifest modeline **Component** ekler. `new ODataModel(...)` ile kurulan ikinci/varyant/`$batch`
modeli, ham `fetch`/`XMLHttpRequest` ve `oModel.sServiceUrl + "…"` ile kurulan URL bunu **almaz** — `sServiceUrl`
sorgusuz saklanır, parametreler `aUrlParams`'tadır. `sap-client`'sız istek tarayıcının tek `sap-usercontext` çerezine
göre yönlenir; çerezi en son açılan client yazar.

**Neden:** Bir ekipte aynı host'un iki client'ı aynı tarayıcıda açılınca ikinci sekmedeki varyant listesi ve veri yazan
yükleme modeli öbür client'ın verisini okudu — hata, dump, 4xx yok; tek client ile yapılan her test yeşildi. Aynı util
birebir kopyalarla birçok uygulamada yaşıyordu ve kanonik şablon da kusuru öğretiyordu.
**Genel ders:** bir çerçeve bir parametreyi **kendi kurduğu nesneye** otomatik ekliyorsa, aynı adresi **elle** kuran her
kod o parametreyi kendisi taşımak zorundadır — eksiklik ancak parametrenin **farklı değer aldığı** bir ortamda görünür.
Tek client / tek dil / tek sekmeyle yapılan test bu sınıfı yapısal olarak yakalayamaz.
**Nasıl uygulanır:** manifest dışı her istekte ana modelin `aUrlParams`'ını (`sap-statistics` hariç) URL sorgusuna
devret — literal client yazma; util'de ana modeli `Component.getOwnerComponentFor(ctrl).getModel()` ile al (onInit'te
view modeli `undefined` olabilir). Kanıt kaynak okuması değil: iki client'lı iki sekme + **ayırıcı veri** (iki client'ta
sayısı farklı entity) + ağ izinde `sap-client`. Kardeş taraması: `new ODataModel(` / `XMLHttpRequest` / `fetch(` /
`sServiceUrl +` tüm uygulamalarda. Reçete `%sap-ui5-fiori` → `freestyle-odata-v2.md` §7.4, kontrol FE-48 / UI-BOOT-06.
İlgili: [UI5 sayfadan ayrılırken senkron XHR](feedback_ui5-sayfadan-ayrilirken-senkron-xhr.md).
Önceki kayıt: yok
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi) · Kapsam: freestyle UI5 + OData V2, çok client'lı host
