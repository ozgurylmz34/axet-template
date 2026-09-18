"""SAP ADT araç modülleri (MCP'siz).

Kayıt, import anında `sapadt._app.profil_tool` dekoratörüyle `REGISTRY`e yapılır:
- meta.py      — ping
- atom.py      — tek-adımlı ADT işlemleri (get / post_shell / push / activate / delete / publish / classrun / msgclass)
- composite.py — çok-adımlı yaratma akışları (domain / dtel / struct)
- query.py     — okuma/sorgu araçları (+ adt_syntax_check ve adt_unit_run: yan etkili, bkz. gate.py)
"""
