# aXet web araçları — kaynak ve doğrulama durumu

> **Kaynak:** aXet.code 1.3.0 (`axetcli.exe`) içindeki araç açıklama metinleri, 2026-09-13'te binary'nin yazdırılabilir
> metin taramasıyla okundu (oturum açılmadı, model çağrısı yapılmadı). "Ofset" metnin binary'deki yaklaşık bayt
> konumudur. Araç açıklaması, aracın modele söylediğidir; davranışın canlı ölçümü değildir.
> **Ölçülmüş olan (aXet.code 1.3.0, model beyanı):** ana modelin gördüğü araç listesi
> (`agentic_fetch`, `download`, `fetch`, `sourcegraph` var; `web_search` yok).
>
> Yeniden doğrulama (template kökünde):
> ```
> python -c "d=open('axetcli.exe','rb').read(); print([d.find(s) for s in (b'Fetches raw content from URL', b'Fetches content from a URL or searches the web', b'Downloads binary data from URL', b'Search code across public repositories')])"
> ```
> `-1` dönen metin o sürümde değişmiş demektir: bu dosyayı güncelle.

| Araç | Açıklama metninden (özet) | Parametreler | Sınırlar | Ofset | Canlı durum |
|---|---|---|---|---|---|
| `fetch` | Adresten ham içerik; yapay zekâ işlemesi yok; analiz/çıkarma gerekiyorsa `agentic_fetch` önerilir | adres, çıktı biçimi (text · markdown · html), isteğe bağlı zaman aşımı — JSON alan adları DOĞRULANMADI | 5MB; yalnız HTTP/HTTPS; kimlik doğrulama/çerez yok; yönlendirmeleri izler; bazı siteler engelleyebilir | ~93117824 | araç listede (ölçüldü); davranış DOĞRULANMADI |
| `agentic_fetch` | Adresi okuyup ya da web'de arayıp yapay zekâ ile işler; `url` verilmezse alt ajan arar; alt ajanın araçları `web_search`, `web_fetch`, `grep`, `view`; salt-okur; `fetch`'ten pahalı | `prompt` (zorunlu), `url` (isteğe bağlı) | sayfa başına 5MB; yalnız HTTP/HTTPS (HTTP → HTTPS); kimlik/çerez yok; arama DuckDuckGo erişilebilirliğine bağlı | ~93188736 | araç listede (ölçüldü); aramalı kullanım DOĞRULANMADI |
| (alt ajan) `web_search` | DuckDuckGo ile arama; başlık, adres, özet döner | `query`, `max_results` (varsayılan 10, en çok 20) | — | ~93032000 | ana modelde yok (ölçüldü); alt ajanda görünürlüğü DOĞRULANMADI |
| (alt ajan) `web_fetch` | Adresi markdown'a çevirip döner; 50KB üstünü geçici dosyaya kaydedip yol verir | adres | 5MB; kimlik/çerez yok | ~93065536 | DOĞRULANMADI |
| `download` | Adresten ikili/metin dosya indirip yerel yola kaydeder; üst klasörleri yaratır | adres, yerel dosya yolu, isteğe bağlı zaman aşımı — JSON alan adları DOĞRULANMADI | 100MB; yalnız HTTP/HTTPS; kimlik/çerez yok; **var olan dosyayı uyarısız ezer** | ~93051808 | araç listede (ölçüldü); davranış DOĞRULANMADI |
| `sourcegraph` | Public repolarda kod araması (Sourcegraph GraphQL API) | `query`, `count` (varsayılan 10, en çok 20), `context_window` (varsayılan 10 satır), `timeout` (en çok 120 sn) | yalnız public repolar; oran sınırı olabilir | ~93145024 | araç listede (ölçüldü); davranış DOĞRULANMADI |

## Notlar
- `agentic_fetch` açıklaması, oturumda `mcp_` önekli bir web okuma aracı varsa onun tercih edilmesini söyler. aXet'te
  yerel MCP yok sayılır (ölçüldü); böyle bir araç ancak merkezi connector üzerinden gelebilir
  (DOĞRULANMADI).
- aXet config şemasında yerleşik araçları kapatan bir `disabled_tools` alanı metni var (örnek değerler `bash`,
  `sourcegraph`); kurumsal kurulumda bir aracın kapatılmış olabileceği anlamına gelir. Bu template'te kullanılmadı,
  davranışı DOĞRULANMADI.
- `agentic_fetch` için ayrı bir izin isteği akışı metni var (binary sembolü); TUI'de izin sorulup sorulmadığı ve
  `permissions.rules` ile kısıtlanıp kısıtlanamadığı DOĞRULANMADI.
